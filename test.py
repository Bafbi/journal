from typing import Any, Generator, Iterator, List, Dict
from lawu.classloader import ClassLoader
import lawu.ast as ast
import getopt
import sys
import json

def check_simple_encode(instructions: List[Any]):
    '''
    [0000]│   ├─<Instruction('getfield')>
    [0000]│   │ └─<FieldReference('net/minecraft/network/protocol/game/ClientboundContainerSetContentPacket', 'containerId', 'I')>
    [0000]│   ├─<Instruction('invokevirtual')>
    [0000]│   │ └─<MethodReference('net/minecraft/network/RegistryFriendlyByteBuf', 'writeByte', '(I)Lnet/minecraft/network/FriendlyByteBuf;')>
    '''
    assert len(instructions) >= 2
    field = None
    assert instructions[1].name == "invokevirtual"
    instruction_method_ref = instructions[1].find_one(name="MethodReference")
    assert instruction_method_ref.class_ == "net/minecraft/network/RegistryFriendlyByteBuf"
    type_ = instruction_method_ref.target
    if instructions[0].name == "getfield":
        field = instructions[0].find_one(name="FieldReference").target
    elif instructions[0].name == "invokevirtual":
        method_ref = instructions[0].find_one(name="MethodReference")
        field = f"{method_ref.class_}.{method_ref.target}"
    elif instructions[0].name == "iconst_0":
        field = "iconst_0"

    # assert instructions[0].name == "getfield"
    # field.append(instructions[0].find_one(name="FieldReference").target)
    # if instructions[1].name == "invokeinterface":
    #     field.append(instructions[1].find_one(name="InterfaceMethodRef").target)
    #     assert instructions[2].name == "invokevirtual"
    #     type_ = instructions[2].find_one(name="MethodReference").target
    # else:
    #     assert instructions[1].name == "invokevirtual"
    #     type_ = instructions[1].find_one(name="MethodReference").target
    # return ".".join(field), type_
    return field, type_

def check_object_encode(instructions: List[Any]):
    '''
    [0000]│   ├─<Instruction('getfield')>
    [0000]│   │ └─<FieldReference('net/minecraft/network/protocol/login/ClientboundCustomQueryPacket', 'payload', 'Lnet/minecraft/network/protocol/login/custom/CustomQueryPayload;')>
    [0000]│   ├─<Instruction('aload_1')>
    [0000]│   ├─<Instruction('invokeinterface')>
    [0000]│   │ ├─<InterfaceMethodRef('net/minecraft/network/protocol/login/custom/CustomQueryPayload', 'write', '(Lnet/minecraft/network/FriendlyByteBuf;)V')>
    [0000]│   │ └─<Number(2)>
    '''
    assert len(instructions) >= 3
    assert instructions[0].name == "getfield"
    assert instructions[1].name == "aload_1"
    assert instructions[2].name == "invokeinterface"
    field = instructions[0].find_one(name="FieldReference").target
    type_ = instructions[2].find_one(name="InterfaceMethodRef").target
    return field, type_

def check_simple_codec(instructions: List[Any], codec_name: str):
    '''
    [0000]│   ├─<Instruction('invokestatic')>
    [0000]│   │ └─<InterfaceMethodRef('net/minecraft/network/codec/ByteBufCodecs', 'byteArray', '(I)Lnet/minecraft/network/codec/StreamCodec;')>
    [0000]│   ├─<Instruction('putstatic')>
    [0000]│   │ └─<FieldReference('net/minecraft/network/protocol/common/ClientboundStoreCookiePacket', 'PAYLOAD_STREAM_CODEC', 'Lnet/minecraft/network/codec/StreamCodec;')>
    '''
    assert len(instructions) >= 2
    assert instructions[0].name == "invokestatic"
    assert instructions[1].name == "putstatic"
    assert instructions[1].find_one(name="FieldReference").target == codec_name
    return instructions[0].find_one(name="InterfaceMethodRef").target

def check_complex_codec(instructions: List[Any], codec_name: str, loader: ClassLoader):
    '''
    We first find the method class then load it and got read the 'encode' method
    [0000]│   ├─<Instruction('invokespecial')>
    [0000]│   │ └─<MethodReference('net/minecraft/world/item/ItemStack$1', '<init>', '()V')>
    [0000]│   ├─<Instruction('putstatic')>
    [0000]│   │ └─<FieldReference('net/minecraft/world/item/ItemStack', 'OPTIONAL_STREAM_CODEC', 'Lnet/minecraft/network/codec/StreamCodec;')>
    '''
    assert len(instructions) >= 2
    assert instructions[0].name == "invokespecial"
    assert instructions[1].name == "putstatic"
    assert instructions[1].find_one(name="FieldReference").target == codec_name
    class_ = instructions[0].find_one(name="MethodReference").class_
    ccf = loader[class_]
    for method in ccf.methods.find():
        print(method)
    encode_method = ccf.methods.find_one(name = "encode", returns = "V")
    print(encode_method.pretty())
    return method_scanner(encode_method, loader)


def check_codec_write(instructions: List[Any], loader: ClassLoader):
    '''
    [0000]│   ├─<Instruction('getstatic')>
    [0000]│   │ └─<FieldReference('net/minecraft/network/protocol/common/ClientboundStoreCookiePacket', 'PAYLOAD_STREAM_CODEC', 'Lnet/minecraft/network/codec/StreamCodec;')>
    [0000]│   ├─<Instruction('aload_1')>
    [0000]│   ├─<Instruction('aload_0')>
    [0000]│   ├─<Instruction('getfield')>
    [0000]│   │ └─<FieldReference('net/minecraft/network/protocol/common/ClientboundStoreCookiePacket', 'payload', '[B')>
    [0000]│   ├─<Instruction('invokeinterface')>
    [0000]│   │ ├─<InterfaceMethodRef('net/minecraft/network/codec/StreamCodec', 'encode', '(Ljava/lang/Object;Ljava/lang/Object;)V')>
    [0000]│   │ └─<Number(3)>
    '''
    assert len(instructions) >= 5
    assert instructions[0].name == "getstatic"
    assert instructions[1].name == "aload_1"
    assert instructions[2].name == "aload_0"
    assert instructions[3].name == "getfield"
    field = instructions[3].find_one(name="FieldReference").target
    assert instructions[4].name == "invokeinterface"
    codec = instructions[0].find_one(name="FieldReference")
    ccf = loader[codec.class_]
    # print(ccf.methods.find_one(name = "<clinit>", returns = "V").pretty())
    codec_instruction = list(ccf.methods.find_one(name = "<clinit>", returns = "V").code.find(name= "Instruction"))
    # print(codec_instruction)
    codec_name = instructions[0].find_one(name="FieldReference").target
    type_ = None
    while len(codec_instruction) > 0:
        try:
            type_ = check_simple_codec(codec_instruction, codec_name)
        except AssertionError:
            pass
        try:
            type_ = check_complex_codec(codec_instruction, codec_name, loader)
        except AssertionError:
            pass
        codec_instruction = codec_instruction[1:]
    return field, type_

def method_scanner(method: ast.Method, loader: ClassLoader) -> Dict[str, Any]:
    print(method.pretty())
    instructions = list(method.code.find(name="Instruction"))
    writes: Dict[str, Any] = {}
    while len(instructions) > 0:
        try:
            field = check_simple_encode(instructions)
            writes[field[0]] = field[1]
        except AssertionError:
            pass
        try:
            field = check_object_encode(instructions)
            writes[field[0]] = field[1]
        except AssertionError:
            pass
        try:
            field = check_codec_write(instructions, loader)
            writes[field[0]] = field[1]
        except AssertionError:
            pass
        instructions = instructions[1:]
    return writes


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



    # cf = loader["net/minecraft/network/protocol/common/ClientboundDisconnectPacket"]
    # cf = loader["net/minecraft/network/protocol/common/ClientboundResourcePackPushPacket"]
    # cf = loader["net/minecraft/network/protocol/game/ClientboundAddExperienceOrbPacket"]
    # cf = loader["net/minecraft/network/protocol/login/ClientboundCustomQueryPacket"]
    # cf = loader["net/minecraft/network/protocol/common/ClientboundStoreCookiePacket"]
    cf = loader["net/minecraft/network/protocol/game/ClientboundContainerSetContentPacket"]

    is_record = cf.attributes.find_one(type_ = ast.UnknownAttribute, f=lambda x: x.name == "Record") is not None
    use_write = cf.methods.find_one(name = "write", returns = "V") is not None
    print(f"Is record: {is_record}, use write: {use_write}")

    method = cf.methods.find_one(name = "write", returns = "V")
    # print(method.pretty())

    structure = method_scanner(method, loader)

    print(structure)
