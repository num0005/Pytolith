from dataclasses import dataclass as _dataclass, field as _field
from enum import Enum as _Enum
import struct as _struct
import functools as _functools
import io as _io

def __string_to_tag(string: str, is_big_endian: bool):
	assert len(string) <= 4, "String too long to be 4 byte tag!"

	string = string.ljust(4, '\0')

	if not is_big_endian:
		string = string[::-1]

	return bytes(string, 'utf-8')


@_functools.total_ordering
class EngineTag(_Enum):
    # halo 1 types
    H1 = "blam"
    # halo 2 types
    H2V1 = "ambl"
    H2V2 = "LAMB"
    H2V3 = "MLAB"
    H2V4 = "BLM!"
    H2Latest = H2V4
    
    # from https://stackoverflow.com/a/58362774
    def __gt__(self, other):
        if not isinstance(other, EngineTag):
            return NotImplemented
        return (
            self._member_names_.index(self.name) >
            self._member_names_.index(other.name)
        )
    
    def __eq__(self, other):
        if other is not EngineTag:
            return NotImplemented
        return self.value == other.value

ENGINE_TAGS = [item.value for item in EngineTag]


@_dataclass(slots=True)
class Header:
    # (mostly) unused in retail
    unused_header: int = 0
    name: str = ""
    
    # 4 character group tag
    group_tag: str = 0

    # crc32 checksum of the tag data
    checksum: int = 0

    data_offset: int = 0x40
    data_size: int = -1 # not used anymore
    unused: int = 0
    version: int = 0
    dest_foundation: int = 0
    current_foundation_index: int = -1# -1 means not in foundation file

    engine_tag: EngineTag = _field(default_factory=lambda: EngineTag.H2Latest)

    is_big_endian: bool = False
    
    @property
    def old_fieldset_header(self):
        """Should the old (short) fieldset header be used?"""
        return self.engine_tag <= EngineTag.H2V1
    @property
    def old_string_id_format(self):
        """Should string ID be included in-line?"""
        return self.engine_tag <= EngineTag.H2V2
    @property
    def include_useless_padding(self):
        """Should useless padding be included in the tag?"""
        return self.engine_tag <= EngineTag.H2V3

    def _get_packing_string(self):
        return f'{">" if self.is_big_endian else "<"}i32s4siiiihbb4s'
    
    def read(self, input_stream: _io.BufferedIOBase):
        header_bytes = input_stream.read(64)
        
        engine_tag = header_bytes[-4:]
        engine_tag = engine_tag.decode("ascii")

        self.is_big_endian = False
        if engine_tag in ENGINE_TAGS:
            self.is_big_endian = True
        
        del engine_tag


        header_struct = _struct.unpack(self._get_packing_string(), header_bytes)

        self.unused_header = header_struct[0]
        self.name = header_struct[1].decode('utf-8', 'replace').split('\x00', 1)[0].strip('\x20')
        tag_group = header_struct[2].decode('utf-8', 'replace')
        if not self.is_big_endian:
            tag_group = tag_group[::-1]

        self.group_tag = tag_group
        self.checksum = header_struct[3]
        self.data_offset = header_struct[4]
        self.data_size = header_struct[5]
        self.unused = header_struct[6]
        self.version = header_struct[7]
        self.dest_foundation = header_struct[8]
        self.current_foundation_index = header_struct[9]
        engine_tag = header_struct[10].decode('utf-8', 'replace')
        if not self.is_big_endian:
            engine_tag = engine_tag[::-1]

        self.engine_tag = EngineTag(engine_tag)

    def write(self, output_stream: _io.BufferedIOBase):
        header = (self.unused_header,
                    bytes(self.name, 'utf-8'),
                    __string_to_tag(self.group_tag, self.is_big_endian),
                    self.checksum,
                    self.data_offset,
                    self.data_length,
                    self.unused,
                    self.version,
                    self.dest_foundation,
                    self.current_foundation_index,
                    __string_to_tag(self.engine_tag, self.is_big_endian))

        output_stream.write(_struct.pack(self._get_packing_string(), *header))