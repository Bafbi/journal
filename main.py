import argparse
import json
import logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG, format='[%(name)s] - %(levelname)s - %(message)s')

import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from lawu.classloader import ClassLoader
from lawu.cf import ClassFile as Class
from lawu._instruction import Instruction
from lawu.ast import *

from codec import CodecAssignmentType, Composite, PacketCodec, Unit
import bootstrap_methods  # Ensure BootstrapMethodsAttribute is registered

# Configure logging
# Use INFO for production, DEBUG for development/troubleshooting
logger = logging.getLogger(__name__)

# Constants
PROTOCOLS = [
    "common", "configuration", "cookie", "game", "handshake", "login", "ping", "status"
]
# PROTOCOLS = [
#     "common"
# ]
BASE_PACKETS_PATH = "net/minecraft/network/protocol"
DEBUG_PACKET = ["net/minecraft/network/protocol/game/ClientboundAddEntityPacket"]

@dataclass
class PacketInfo:
    """A dataclass to hold structured information about a packet."""
    id: int
    name: str
    side: str
    state: str
    class_path: Optional[str]
    structure: Optional[Dict[str, str]]
    
def _parse_packet_class_from_signature(signature: str) -> Optional[str]:
    """Extracts the packet class path from a generic signature string."""
    try:
        generic_part = signature.split('<', 1)[1].rsplit('>', 1)[0]
        if generic_part.startswith('L') and generic_part.endswith(';'):
            return generic_part[1:-1]
    except IndexError:
        logger.warning(f"Could not parse signature: {signature}")
    return None
  
def _resolve_invokedynamic_target_method(pcf: Class, instr: Instruction) -> Optional[str]:
    """
    Resolves an invokedynamic instruction to find the name of its target method.
    This is used to find the real methods behind method references (e.g., ::write).
    """
    invoke_dynamic_node: InvokeDynamic = instr.find_one(name="InvokeDynamic")
    if invoke_dynamic_node == None:
        logger.warning(f"Instruction was not an invokedynamic call: {instr}")
        return None


    logger.debug(f"Resolving invokedynamic instruction: \n{invoke_dynamic_node.pretty()}")
    bootstrap_index = invoke_dynamic_node.bootstrap_index
    logger.debug(f"Bootstrap index for invokedynamic: {bootstrap_index}")

    # Log all attributes in the class file for debugging
    logger.debug(f"Attributes in class file {pcf.this}: {[attr for attr in pcf.attributes.find()]}")
    
    # Find the BootstrapMethods attribute in the class file
    bootstrap_methods_attr = pcf.attributes.find_one(type_=UnknownAttribute, f=lambda a: a.name == "BootstrapMethods")
    if bootstrap_methods_attr is None:
        logger.warning(f"No BootstrapMethods attribute found in class {pcf.this}")
        return None
    logger.debug(f"Found BootstrapMethods attribute: {bootstrap_methods_attr}")
    ## log the payload of the BootstrapMethods attribute, converting from "b'\x00\x02\x01\x1d\x00\x03\x01\x11\x01\x14\x01\x16\x01\x1d\x00\x03\x01!\x01$\x01&'" it to a readable string for readability
    logger.debug(f"BootstrapMethods payload: {bootstrap_methods_attr.payload.decode('utf-8')}")

    # if bootstrap_methods_attr is None or bootstrap_index >= len(bootstrap_methods_attr.bootstrap_methods):
    #     logger.warning(f"Could not find bootstrap method at index {bootstrap_index} in {pcf.this}")
    #     return None

    bootstrap_method = bootstrap_methods_attr.bootstrap_methods[bootstrap_index]
    
    # The bootstrap arguments contain a MethodHandle to the actual implementation method.
    for arg in bootstrap_method.arguments:
        # lawu represents this as a Constant node with a name containing 'MethodHandle'
        if 'MethodHandle' in arg.name:
            # The 'constant' attribute of this node holds the details (name, class, etc.)
            method_handle = arg.constant
            # We want the name of the method, e.g., "write" or "new"
            return method_handle.name

    logger.warning(f"Could not find a MethodHandle in bootstrap arguments for instruction {instr}")
    return None

def _get_structure_from_composite(instructions: List[Instruction], start_index: int) -> Dict[str, str]:
    """
    Parses the arguments to a StreamCodec.composite() call to find the packet structure.
    Walks backwards from the `invokestatic` call, collecting codec-getter pairs.
    """
    structure = {}
    # Walk backwards from the instruction before the invokestatic call
    i = start_index - 1
    while i > 0:
        getter_instr = instructions[i]
        codec_instr = instructions[i - 1]

        # The pattern is: getstatic (codec), ldc (getter method handle)
        if not (codec_instr.name == 'getstatic' and getter_instr.name == 'ldc'):
            # End of the argument list
            break

        codec_ref = codec_instr.find_one(name="FieldReference")
        # In modern lawu, MethodHandle might be nested. Find it robustly.
        method_handle_node = getter_instr.find_one(lambda n: 'MethodHandle' in n.name)
        
        if codec_ref and method_handle_node:
            method_handle = method_handle_node.constant
            # Getter name e.g. 'getPos', 'getType'. We extract the field name.
            field_name_match = re.match(r'^get([A-Z])(.*)$', method_handle.name)
            if field_name_match:
                field_name = field_name_match.group(1).lower() + field_name_match.group(2)
            else:
                 # Fallback for non-standard getter names
                field_name = method_handle.name

            # Type is represented by the codec's class and field name
            codec_type = f"{codec_ref.class_}.{codec_ref.target}"
            structure[field_name] = codec_type
        
        i -= 2 # Move to the next pair

    # The fields are parsed backwards, so we reverse them to match declaration order
    return dict(reversed(list(structure.items())))


def _get_structure_from_write_method(pcf: Class) -> Optional[Dict[str, str]]:
    """
    Analyzes the packet's `write` method to determine its data structure.
    This is the fallback method for packets using Packet.codec(write, new).
    """
    try:
        write_method = pcf.methods.find_one(name="write")
        code = write_method.code
    except (AttributeError, StopIteration):
        logger.debug(f"Packet class {pcf.this} has no 'write' method.")
        return None

    # The old find_simple/complex types can be combined and simplified
    structure = {}
    last_getfield = None
    instruction_list = list(code.find(name="instruction"))

    for i, instruction in enumerate(instruction_list):
        if instruction.name == 'getfield':
            last_getfield = instruction
        elif instruction.name == 'invokevirtual' and last_getfield:
            field_ref = last_getfield.find_one(name="FieldReference")
            method_ref = instruction.find_one(name="MethodReference")
            if field_ref and method_ref and "write" in method_ref.target:
                structure[field_ref.target] = method_ref.target.split("write", 1)[1]
            last_getfield = None # Reset after use
        elif instruction.name == 'getstatic':
            # Check for the complex pattern: getstatic, aload, aload, getfield
            if i + 3 < len(instruction_list) and instruction_list[i+3].name == 'getfield':
                field_instr = instruction_list[i+3]
                codec_ref = instruction.find_one(name="FieldReference")
                field_ref = field_instr.find_one(name="FieldReference")
                if codec_ref and field_ref:
                    structure[field_ref.target] = f"{codec_ref.class_}.{codec_ref.target}"

    return structure if structure else None

def get_codec_assignment_type(pcf: Class) -> Optional[CodecAssignmentType]:
    """
    Determines the type of codec assignment used in the packet class.
    Returns a CodecAssignmentType instance if found, otherwise None.
    """
    try:
        clinit_method = pcf.methods.find_one(name="<clinit>")
        logger.debug(f"\n{clinit_method.pretty()}")

        # The .find() method from lawu returns a generator, so we convert it to a list
        instructions: list[Instruction] = list(clinit_method.code.find(name="instruction"))
    except (AttributeError, StopIteration):
        # No static initializer means no STREAM_CODEC is defined in this way.
        return None

    for i, instruction in enumerate(instructions):
      if instruction.name == 'putstatic':
          field_ref: FieldReference = instruction.find_one(name="FieldReference")
          if field_ref is not None and field_ref.target == 'STREAM_CODEC':
              # We found the assignment. Now look at the instruction(s) that created the value.
              creator_instr = instructions[i - 1]
              
              if creator_instr.name == 'invokestatic':
                  method_ref = creator_instr.find_one(name="InterfaceMethodRef")
                  if method_ref is None:
                      continue

                  logger.debug(f"Found STREAM_CODEC created by invokestatic call to {method_ref.class_}.{method_ref.target}")

                  if method_ref.target == 'unit':
                      return Unit()
                  elif method_ref.target == 'composite':
                      # You would add logic here to parse the composite arguments
                      return Composite(codec_names=[])
                  elif method_ref.class_ == 'net/minecraft/network/protocol/Packet' and method_ref.target == 'codec':
                      # This is our target case. The arguments are the two instructions before this one.
                      if i < 3:
                          logger.warning("Found Packet.codec call without enough arguments on the stack.")
                          continue
                      
                      writer_instr = instructions[i - 3]
                      logger.debug(f"Found Packet.codec with writer instruction: \n{writer_instr.pretty()}")
                      reader_instr = instructions[i - 2]
                      logger.debug(f"Found Packet.codec with reader instruction: \n{reader_instr.pretty()}")

                      if writer_instr.name != 'invokedynamic' or reader_instr.name != 'invokedynamic':
                          logger.warning(f"Expected two invokedynamic calls for Packet.codec, but got {writer_instr.name} and {reader_instr.name}")
                          continue
                      
                      # Resolve each invokedynamic call to get the method names
                      writer_method = _resolve_invokedynamic_target_method(pcf, writer_instr)
                      reader_method = _resolve_invokedynamic_target_method(pcf, reader_instr)

                      logger.debug(f"Resolved Packet.codec to writer='{writer_method}' and reader='{reader_method}'")
                      return PacketCodec(writer_method=writer_method, reader_method=reader_method)

              elif creator_instr.name == 'getstatic':
                  # This covers the INSTANCE case, e.g., for empty packets
                  return Unit()

    return None

def get_packet_structure(pcf: Class) -> Optional[Dict[str, str]]:
    """
    Analyzes a packet class to find its structure, prioritizing the STREAM_CODEC field.
    """
    codec_assignment_type = get_codec_assignment_type(pcf)
    if codec_assignment_type is None:
        logger.warning(f"Packet {pcf.this} has no recognized codec assignment type.")
        return None
    structure = {"codec_assignment_type": codec_assignment_type.__class__.__name__}
    logger.debug(f"Packet {pcf.this} codec assignment type: {codec_assignment_type}")
    match codec_assignment_type:
        case Unit():
            logger.debug(f"Packet {pcf.this} is a Unit codec assignment.")
        case Composite(codec_names):
            logger.debug(f"Packet {pcf.this} is a Composite codec assignment with codecs: {codec_names}")
            structure["composite_codecs"] = codec_names
        case PacketCodec(writer, reader):
            logger.debug(f"Packet {pcf.this} is a PacketCodec assignment with writer: {writer} and reader: {reader}")
            structure.update({"data": {
                "writer": writer.__name__ if writer else None,
                "reader": reader.__name__ if reader else None
            }})
        case _:
            logger.error(f"Unknown codec assignment type for packet {pcf.this}: {codec_assignment_type}")
    return structure if structure else None


def extract_packets(loader: ClassLoader) -> List[PacketInfo]:
  """Main extraction logic that iterates through protocols and their packets."""
  all_packets = []
  debug_mode = bool(DEBUG_PACKET)
  debug_packet_set = set(DEBUG_PACKET)

  for protocol in PROTOCOLS:
    logger.info(f"Processing protocol state: {protocol}")
    types_class_path = f"{BASE_PACKETS_PATH}/{protocol}/{protocol.capitalize()}PacketTypes"

    try:
      cf = loader[types_class_path]
    except KeyError:
      logger.warning(f"Could not find packet registry class: {types_class_path}")
      continue

    for packet_id, field in enumerate(cf.fields.find()):
      side, *name_parts = field.name.split("_")
      packet_name = "_".join(name_parts)

      signature = field.find_one(name="Signature")
      if signature is None:
        logger.warning(f"Field {field.name} in {types_class_path} has no signature.")
        continue

      packet_class_path = _parse_packet_class_from_signature(signature.signature.value)

      # Only analyze packets in DEBUG_PACKET if DEBUG_PACKET is non-empty
      if debug_mode:
        if not packet_class_path or packet_class_path not in debug_packet_set:
          continue

      structure = None

      if packet_class_path and packet_class_path in loader:
        logger.debug(f"Analyzing packet class: {packet_class_path}")
        pcf = loader[packet_class_path]
        structure = get_packet_structure(pcf)
      else:
        logger.warning(f"Could not load class for packet {packet_name}: {packet_class_path}")

      packet = PacketInfo(
        id=packet_id,
        name=packet_name,
        side=side,
        state=protocol,
        class_path=packet_class_path,
        structure=structure,
      )
      all_packets.append(packet)
  return all_packets


def main():
    """Main function to parse arguments and run the extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Minecraft packet information from a server.jar file."
    )
    parser.add_argument(
        "-j", "--jar-file", type=Path, required=True, help="Path to the server.jar file."
    )
    parser.add_argument(
        "-o", "--output-file", type=Path, default=Path("packets.json"),
        help="Path to the output JSON file (default: packets.json)."
    )
    args = parser.parse_args()

    if not args.jar_file.is_file():
        logger.error(f"Error: JAR file not found at {args.jar_file}")
        sys.exit(1)

    logger.info(f"Loading class loader for {args.jar_file}...")
    loader = ClassLoader(str(args.jar_file), max_cache=200) # Increased cache for more complex analysis

    packets_data = extract_packets(loader)

    output_data = {
        "size": len(packets_data),
        "packets": [asdict(p) for p in packets_data]
    }

    logger.info(f"Writing {len(packets_data)} packets to {args.output_file}...")
    try:
        with args.output_file.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4)
        logger.info("Extraction complete.")
    except IOError as e:
        logger.error(f"Failed to write to output file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()