from lawu import cf


class PacketFile:
    def __init__(self, cf: cf.ClassFile):
        self.cf = cf

    def get_main_codec(self):
        assert self.cf.fields.find_one(name="STREAM_CODEC") is not None

    def __str__(self):
        return f"{self.packet_id} {self.packet_name} {self.packet_fields}"
