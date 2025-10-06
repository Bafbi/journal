from __future__ import annotations # For Python < 3.9 type hints for generics
from dataclasses import dataclass
from typing import Union, List, Callable, Any

# Define the base class for our "enum"
class CodecAssignmentType:
    """
    Represents the type of codec assignment, mimicking a Rust enum.
    """
    pass

# Define the variants as dataclasses inheriting from the base class

@dataclass(frozen=True) # frozen=True makes instances immutable, like Rust enum variants
class Unit(CodecAssignmentType):
    """
    A simple unit codec assignment (no associated data).
    Corresponds to Rust's `Unit` or `None`.
    """
    pass

@dataclass(frozen=True)
class Composite(CodecAssignmentType):
    """
    A composite codec assignment with a list of codec names.
    Corresponds to Rust's `Composite(Vec<String>)`.
    """
    codec_names: List[str]

# Define types for writer and reader callables for clarity
# For a generic codec, the writer might take Any and return bytes,
# and the reader might take bytes and return Any.
WriterFunc = Callable[[Any], bytes]
ReaderFunc = Callable[[bytes], Any]

@dataclass(frozen=True)
class PacketCodec(CodecAssignmentType):
    """
    A packet codec assignment with specific writer and reader functions.
    Corresponds to Rust's `PacketCodec { writer: Box<dyn Fn(...)>, reader: Box<dyn Fn(...)> }`.
    """
    writer: WriterFunc
    reader: ReaderFunc

# Define a Union type for convenience and type checking
CodecAssignment = Union[Unit, Composite, PacketCodec]

# # --- Example Usage ---

# # 1. Helper functions for PacketCodec variant
# def my_packet_writer(data: str) -> bytes:
#     """Simple writer that encodes string to bytes."""
#     print(f"Writing data: '{data}'")
#     return data.encode('utf-8')

# def my_packet_reader(data_bytes: bytes) -> str:
#     """Simple reader that decodes bytes to string."""
#     decoded = data_bytes.decode('utf-8')
#     print(f"Reading bytes: '{decoded}'")
#     return decoded

# # 2. Creating instances of the CodecAssignmentType
# codec_unit = Unit()
# codec_composite = Composite(codec_names=["h264", "aac", "opus"])
# codec_packet = PacketCodec(writer=my_packet_writer, reader=my_packet_reader)

# # 3. Using structural pattern matching (Python 3.10+)
# def process_codec_assignment(assignment: CodecAssignment):
#     """
#     Processes a CodecAssignmentType using structural pattern matching.
#     """
#     match assignment:
#         case Unit():
#             print("Handling Unit codec assignment: No specific codec needed.")
#         case Composite(names): # Matches Composite and extracts 'codec_names' into 'names'
#             print(f"Handling Composite codec assignment. Codecs in sequence: {', '.join(names)}")
#             # You could iterate through 'names' here to apply codecs
#             for name in names:
#                 print(f"  - Processing sub-codec: {name}")
#         case PacketCodec(writer=w, reader=r): # Matches PacketCodec and extracts 'writer' and 'reader'
#             print("Handling PacketCodec assignment. Specific writer/reader functions provided.")
#             # Use the extracted functions
#             test_data = "Hello Codec World!"
#             encoded_data = w(test_data)
#             decoded_data = r(encoded_data)
#             print(f"  Test data '{test_data}' -> Encoded -> Decoded: '{decoded_data}'")
#             # You can also use positional extraction if the dataclass fields are always in a known order:
#             # case PacketCodec(w, r): # 'w' would be writer, 'r' would be reader
#         case _: # Catch-all for unknown types (though with Union, MyPy would warn if this is reachable)
#             print(f"Unknown codec assignment type: {type(assignment)}")

# print("--- Processing codec_unit ---")
# process_codec_assignment(codec_unit)

# print("\n--- Processing codec_composite ---")
# process_codec_assignment(codec_composite)

# print("\n--- Processing codec_packet ---")
# process_codec_assignment(codec_packet)

# # Example with a list of different assignments
# print("\n--- Processing a list of mixed assignments ---")
# assignments_list: List[CodecAssignment] = [
#     Unit(),
#     Composite(["jpeg", "mp3"]),
#     PacketCodec(writer=lambda x: b"custom_write", reader=lambda x: "custom_read"),
#     Composite(["raw_video"])
# ]

# for i, assignment in enumerate(assignments_list):
#     print(f"\nProcessing assignment #{i+1}:")
#     process_codec_assignment(assignment)