from typing import Any, Generator, Iterator, List, Dict
from lawu.classloader import ClassLoader
import getopt
import sys
import json

PROTOCOLS = [
    "common",
    "configuration",
    "cookie",
    "game",
    "handshake",
    "login",
    "ping",
    "status"
]

PACKETS_PATH = "net/minecraft/network/protocol"


def find_simple_types(instructions: Generator) -> Dict[str, str]:
    types = {}
    pair = []
    for instruction in instructions:
        if instruction.name == "getfield" and len(pair) == 0:
            pair.append(instruction)
        elif instruction.name == "invokevirtual" and len(pair) == 1:
            pair.append(instruction)
            # get the field name and the type
            field = pair[0].find_one(name="FieldReference").target
            type_ = pair[1].find_one(name="MethodReference").target
            types[field] = type_.split("write")[1]
            pair = []
    return types

def find_complex_types(instructions: Generator) -> Dict[str, str]:
    '''
    The instruction set we are looking for is:
        [0000]│ ├─<Instruction('getstatic')>
        [0000]│ │ └─<FieldReference('net/minecraft/world/item/ItemStack', 'OPTIONAL_LIST_STREAM_CODEC', 'Lnet/minecraft/network/codec/StreamCodec;')>
        [0000]│ ├─<Instruction('aload_1')>
        [0000]│ ├─<Instruction('aload_0')>
        [0000]│ ├─<Instruction('getfield')>
        [0000]│ │ └─<FieldReference('net/minecraft/network/protocol/game/ClientboundContainerSetContentPacket', 'items', 'Ljava/util/List;')>
        [0000]│ ├─<Instruction('invokeinterface')>
        [0000]│ │ ├─<InterfaceMethodRef('net/minecraft/network/codec/StreamCodec', 'encode', '(Ljava/lang/Object;Ljava/lang/Object;)V')>
        [0000]│ │ └─<Number(3)>

    from the above instruction set we can see that the field is named `items` and the type is `Ljava/util/List;` but also the type of the field is the return value from `OPTIONAL_LIST_STREAM_CODEC`
    '''
    types = {}
    pair = []
    for instruction in instructions:
        # print(pair, instruction.name)
        if instruction.name == "getstatic" and len(pair) == 0:
            pair.append(instruction)
        elif "aload" in instruction.name and (len(pair) == 1 or len(pair) == 2):
            pair.append(instruction)
        elif instruction.name == "getfield" and len(pair) == 3:
            pair.append(instruction)
            # get the field name and the type
            field = pair[3].find_one(name="FieldReference").target
            ref = pair[0].find_one(name="FieldReference")
            type_ = f"{ref.class_}.{ref.target}"
            types[field] = type_
            pair = []
    return types

def find_types(code) -> Dict[str, str]:
    types_s = find_simple_types(code.find(name="instruction"))
    # print(types_s)
    types_c = find_complex_types(code.find(name="instruction"))
    # print(types_c)

    # combine the two types
    types = {**types_s, **types_c}
    # print(types)
    return types

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "j:")
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)

    jar_file = None
    for o, a in opts:
        if o == "-j":
            jar_file = a

    loader = ClassLoader(jar_file, max_cache=50)
    # for types_class_path in loader.classes:
    #     print(types_class_path)



    # write packets into a json file
    packets_json = {
        "packets": [],
        "size": 0
    }
    for protocol in PROTOCOLS:
        types_class_path = f"{PACKETS_PATH}/{protocol}/{protocol.capitalize()}PacketTypes"
        cf = loader[types_class_path]
        for id, field in enumerate(cf.fields.find()):
            # print(field.pretty())
            # CLIENTBOUND_CUSTOM_PAYLOAD
            name ="_".join(field.name.split("_")[1:])
            side = field.name.split("_")[0]
            packet_class_path = field.find_one(name="Signature").signature.value.split("<")[1].split(">")[0][1:-1]
            # from : Lnet/minecraft/network/protocol/PacketType<Lnet/minecraft/network/protocol/status/ServerboundStatusRequestPacket;>;
            # to : net/minecraft/network/protocol/status/ServerboundStatusRequestPacket
            print(packet_class_path)
            types = None
            found = False
            if packet_class_path in loader:
                print("found")
                found = True
                pcf = loader[packet_class_path]
                try:
                    code = pcf.methods.find_one(name="write").code
                    types = find_types(code)
                except:
                    pass


            packet = {
                "id": -1,
                "name": name,
                "side": side,
                "state": protocol,
                "class": packet_class_path if found else None,
                "structure": types,
            }



            packets_json["packets"].append(packet)





    json.dump(packets_json, open("packets.json", "w"), indent=4)
