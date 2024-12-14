from __future__ import annotations as _
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
import struct as _struct
import typing as _typing
from Pytolith.Definitions import Definitions as _Definitions, TagGroup as _TagGroup
from Pytolith.Definitions.Fields import FieldArrayDef as _FieldArrayDef
from Pytolith.Definitions.Layout import FIELDS_TYPE,FIELD_TYPE, LayoutDef as _LayoutDef
from Pytolith.TagTypes import EulerAngles2D as _EulerAngles2D, EulerAngles3D as _EulerAngles3D, Point2D as _Point2D, RealPlane2D as _RealPlane2D
from Pytolith.TagTypes import RealPlane3D as _RealPlane3D, Rectangle2D as _Rectangle2D, TagField as _TagField, TagFieldElement as _TagFieldElement, TagReference as _TagReference
from Pytolith.TagTypes import TagBlock as _TagBlock, TagStruct as _TagStruct, TagGroupData as _TagGroupData, TagLayoutConfig as _TagLayoutConfig
from Pytolith.TagLoader.Header import Header as _Header
import io as _io
import collections.abc as _abc
import platform

def __load_fast_definitions():
	if platform.python_implementation() == "PyPy":
		return None, None
	try:
		from Pytolith.TagLoader._FastTagLoaders import LAYOUT_READERS, LAYOUT_VERSION
		return LAYOUT_READERS,LAYOUT_VERSION
	except:
          return None,None


_FAST_LAYOUT_READERS,_FAST_READERS_VERSION = __load_fast_definitions()

class _ByteStream:
	class EOF(ValueError):
		pass
	__slots__ = ("array", "offset", "length")
	def __init__(self, array: '_abc.Buffer'):
		self.array = memoryview(array).toreadonly()
  
		assert self.array.itemsize == 1
		assert self.array.ndim == 1
  
		self.offset = 0
		self.length = len(self.array)
  
	def read(self, size: int):
		if self.offset + size > self.length:
			raise _ByteStream.EOF(f"Not enough space in stream to read {size} bytes ({size}>{len(self.array)-self.offset})!")
		return_data = self.array[self.offset : self.offset+size]
		self.offset += size
		return return_data

	def skip(self, size):
		if self.offset + size > self.length:
			raise _ByteStream.EOF("Reached end of stream while trying to skip forward!")
		self.offset += size

	def read_string(self, length):
		return self.read(length).tobytes().decode(errors="surrogateescape")

	def length_left(self):
		return self.length - self.offset

@_dataclass(slots=True, frozen=True)
class _TagReaderCache:
     # basic types (used by fast loaders)
	s_real: _struct.Struct
	s_long: _struct.Struct
	s_ulong: _struct.Struct
	s_short: _struct.Struct
	s_ushort: _struct.Struct
	s_char: _struct.Struct
	s_uchar: _struct.Struct
	s_2short: _struct.Struct
	s_2real: _struct.Struct
	s_3real: _struct.Struct
	s_4real: _struct.Struct
     # layout types
	s_tag_reference: _struct.Struct
	s_tag_block: _struct.Struct
	# basic readers that don't need the field definition
	read_cc4: _typing.Callable[[_ByteStream], str]
	read_real: _typing.Callable[[_ByteStream], float]
	read_char_integer: _typing.Callable[[_ByteStream], int]
	read_short_integer: _typing.Callable[[_ByteStream], int]
	read_long_integer: _typing.Callable[[_ByteStream], int]
	read_uchar_integer: _typing.Callable[[_ByteStream], int]
	read_ushort_integer: _typing.Callable[[_ByteStream], int]
	read_ulong_integer: _typing.Callable[[_ByteStream], int]
	read_two_shorts: _typing.Callable[[_ByteStream], tuple[int, int]]
	read_two_reals: _typing.Callable[[_ByteStream], tuple[float, float]]
	read_three_reals: _typing.Callable[[_ByteStream], tuple[float, float, float]]
	read_four_reals: _typing.Callable[[_ByteStream],  tuple[float, float, float, float]]
	read_rect: _typing.Callable[[_ByteStream], _Rectangle2D]
	read_point2d: _typing.Callable[[_ByteStream], _Point2D]
	# more complex readers that need the field definition
	read_pad_field: _typing.Callable[[_ByteStream, FIELD_TYPE], bytes]
 
 
	cache: _typing.ClassVar[dict[bool, _TagReaderCache]] = dict()
 
	@staticmethod
	def get(endianness: str, is_big_endian: bool):
		try:
			return _TagReaderCache.cache[is_big_endian]
		except:
			cache =_TagReaderCache.cache[is_big_endian] = _TagReaderCache._generate_cache(endianness, is_big_endian)
			_TagReaderCache.cache[is_big_endian] = cache
			return cache
 
	@staticmethod
	def _generate_cache(endianness: str, is_big_endian: bool):
		# primitve type structures
		s_real = _struct.Struct(endianness + "f")
		s_long = _struct.Struct(endianness + "l")
		s_ulong = _struct.Struct(endianness + "L")
		s_short = _struct.Struct(endianness + "h")
		s_ushort = _struct.Struct(endianness + "H")
		s_char = _struct.Struct(endianness + "b")
		s_uchar = _struct.Struct(endianness + "B")
		# tag types
		s_2short = _struct.Struct(endianness + "hh")
		s_rect2d = _struct.Struct(endianness + "hhhh")
		s_2real = _struct.Struct(endianness + "ff")
		s_3real = _struct.Struct(endianness + "fff")
		s_4real = _struct.Struct(endianness + "ffff")
		# complex tag types
  
		# tag reference (editor) layout:
		# tag: cc4, tag type
		# path_pointer: u4, is invalid/garbage on disk
		# path_length: u4
		# tag_index: u4, is invalid/garbage on disk
		s_tag_reference = _struct.Struct(endianness + "4xL4x")
		# tag block (editor) layout:
		# count: u4
		# elements: void* # invalid/garbage on disk
		# defintion: void* # invalid/garbage on disk
		s_tag_block = _struct.Struct(endianness + "LLL")
  
		#######
		# Field-less readers
		#
		# These readers do not take the tag field definition as an argument
		#######
  
		if is_big_endian:
			def read_cc4(es: _ByteStream):
				return es.read_string(4)
		else:
			def read_cc4(es: _ByteStream) -> str:
				string = es.read_string(4)
				return string[::-1]
		def read_real(es: _ByteStream) -> float:
			return s_real.unpack(es.read(4))[0]
		def read_char_integer(es: _ByteStream) -> int:
			return s_char.unpack(es.read(1))[0]
		def read_short_integer(es: _ByteStream) -> int:
			return s_short.unpack(es.read(2))[0]
		def read_long_integer(es: _ByteStream) -> int:
			return s_long.unpack(es.read(4))[0]
		def read_uchar_integer(es: _ByteStream) -> int:
			return s_uchar.unpack(es.read(1))[0]
		def read_ushort_integer(es: _ByteStream) -> int:
			return s_ushort.unpack(es.read(2))[0]
		def read_ulong_integer(es: _ByteStream) -> int:
			return s_ulong.unpack(es.read(4))[0]
		def read_two_shorts(es: _ByteStream) -> tuple[int, int]:
			return s_2short.unpack(es.read(4))
		def read_two_reals(es: _ByteStream) -> tuple[float, float]:
			return s_2real.unpack(es.read(8))
		def read_three_reals(es: _ByteStream) -> tuple[float, float]:
			return s_3real.unpack(es.read(12))
		def read_four_reals(es: _ByteStream) -> tuple[float, float]:
			return s_4real.unpack(es.read(16))
		def read_rect(es: _ByteStream):
			temp = s_rect2d.unpack(es.read(8))
			value = _Rectangle2D(*temp)
			return value
		def read_point2d(es: _ByteStream):
			return _Point2D(*read_two_shorts(es))

		#######
		# Field-based readers
		#
		# These readers require the field definition to work
		#######

		def read_pad_field(es: _ByteStream, field_def: FIELD_TYPE):
			if field_def.tag == 'pd64':
				return None
			try:
				return bytes(es.read(field_def.length))
			except:
				return es.read(es.length_left())

		return _TagReaderCache(
					s_real = s_real,
					s_long = s_long,
					s_ulong = s_ulong,
					s_short = s_short,
					s_ushort = s_ushort,
					s_char = s_char,
					s_uchar = s_uchar,
					s_2short = s_2short,
					s_2real = s_2real,
					s_3real = s_3real,
					s_4real = s_4real,
       				s_tag_reference=s_tag_reference,
                         s_tag_block=s_tag_block,
                         read_cc4=read_cc4,
                         read_real=read_real,
                         read_char_integer=read_char_integer,
                         read_short_integer=read_short_integer,
                         read_long_integer=read_long_integer,
                         read_uchar_integer=read_uchar_integer,
                         read_ushort_integer=read_ushort_integer,
                         read_ulong_integer=read_ulong_integer,
                         read_two_shorts=read_two_shorts,
                         read_two_reals=read_two_reals,
                         read_three_reals=read_three_reals,
                         read_four_reals=read_four_reals,
                         read_rect=read_rect,
                         read_point2d=read_point2d,
                         read_pad_field=read_pad_field)



class _TagLoadingState:
	__slots__ = ("_tag_group_mapping","_stream","_header","_group_def","_s_tbfd",
              "_fast_tag_loaders",
              "_tag_readers", "_tag_readers_special_field",
              "s_real", "s_long", "s_ulong", "s_short", "s_ushort", "s_char",
              "s_uchar", "s_2short", "s_2real", "s_3real", "s_4real")
  
	class FieldSetTypes(str,_Enum):
		TagBlockFieldData = 'tbfd'
		TagStructFieldData = 'tsfd'
	
	def __init__(self, tag_group_mapping: _typing.Dict[str, _TagGroup], stream: _io.BufferedIOBase, version_hash: bytes):
		self._tag_group_mapping = tag_group_mapping
		self._stream = stream
		self._header = _Header()
		self._group_def = None
		self._s_tbfd = None
		self._tag_readers = None

		if _FAST_READERS_VERSION == version_hash:
			self._fast_tag_loaders = _FAST_LAYOUT_READERS
		else:
			# bad version todo print a warning message here?
			# this shouldn't really happen
			self._fast_tag_loaders = None
	
	def read_header(self):
		# read header and seek straight to data + setup definition
		self._header.read(self._stream)
		self._stream.seek(self._header.data_offset)

		if not self._header.group_tag in self._tag_group_mapping:
			raise ValueError(f"No tag definitions exist for this files tag group: {self._header.group_tag}")

		self._group_def = self._tag_group_mapping[self._header.group_tag]

		if self._group_def.version != self._header.version:
			raise ValueError(f"Unsupported tag version set in header (got {self._header.version} expected {self._group_def.version})")

		self._s_tbfd = _struct.Struct(self.endianness + "hhl" if self._header.old_fieldset_header else "lll")
  
	def read(self) -> _TagGroupData:
		self.read_header()
		self._setup_tag_readers()
		root_tag_block = self._read_tag_block(self._group_def.layout, 1)
		return _TagGroupData(root_tag_block, self._group_def)

	def _read_tag_block(self, layout: _LayoutDef, block_count: int) -> _TagBlock:
		versioned_layout, count = self._read_field_set_header(layout, self.FieldSetTypes.TagBlockFieldData)
  
		if count is None:
			count = block_count
		if count != block_count and block_count is not None:
			raise ValueError(f"Unexpected number of elements for tag block, expected {block_count}, got {count}")

		elements: list[_TagFieldElement] = []

		# load field data
		element_size = versioned_layout.element_size
		elements_buffers = []
		for _ in range(count):
			elem_buffer = self._stream.read(element_size)
			if len(elem_buffer) != element_size:
				raise ValueError(f"Unexpected end of stream while reading layout {layout.unique_id}")
			elements_buffers.append(elem_buffer)

		for i in range(count):
			element_stream = _ByteStream(elements_buffers[i])
			element_fields = self._parse_field_data_element(element_stream, versioned_layout)

			elements.append(element_fields)
			# dispose
			del element_stream
			elements_buffers[i] = None
		del elements_buffers # dispose
		return _TagBlock(versioned_layout, elements)
	
	def _read_field_set_header(self, layout: _LayoutDef, header_type: FieldSetTypes):
		old_stream_pos = self._stream.tell()
		try:
			header_len = (2*2 + 4) if self._header.old_fieldset_header else 4*3
		
			tag = self.read_cc4()
			(version, count, element_size) = self._s_tbfd.unpack(self._stream.read(header_len))
			if not tag == layout.tag_block_field_header_tag and tag != header_type:
				raise ValueError(f"Invalid tag field data header tag got {tag} != {layout.tag_block_field_header_tag} when reading layout {layout.unique_id}")
		except Exception as err:
			print(f"{type(err)}: {err}")
			print(f"Failed to read fieldset header, assuming old format!")
			self._stream.seek(old_stream_pos)
			version = 0
			count = None
			element_size = layout.versions[0].sizeof_override
			if element_size is None:
				element_size = layout.versions[0].sizeof_for_config(self._header.include_useless_padding, self._header.old_string_id_format)
		# workaround to load older versions of vertex_shader, keep the version set here in sync with the tag definitions
		if layout.unique_id == "block:vertex_shader" and version == 0 and element_size == 20:
			version = 1
   
		fast_loader = None
		try:
			fast_loader = _FAST_LAYOUT_READERS[layout.unique_id][version]
		except:
			pass
			
		versioned_layout = _TagLayoutConfig(layout, version, element_size, fast_loader)
		if not versioned_layout.is_version_valid:
			raise ValueError(f"Version {version} is not supported for layout {layout.unique_id}")

		return versioned_layout, count

	def _read_struct_data(self, versioned_layout: _TagLayoutConfig, stream: _ByteStream):
		struct_fields = self._parse_field_data_element(stream, versioned_layout)
		return _TagStruct(versioned_layout, struct_fields)

	def _parse_field_data_element(self, element_stream: _ByteStream, layout: _TagLayoutConfig):
		field_set_def = layout.fieldset_defintion
		fast_loader = layout._fast_loader
		if fast_loader:
			fields_data = []
			try:
				fast_loader(self, element_stream, field_set_def.merged_fields, fields_data)
			except _ByteStream.EOF as eof:
				# check if the stream ended at a field boundry
				# if it did this could be a valid truncated tag created by implicit versioning (append)
				# if not we either read the tag wrong or it's most likely corrupt
				if element_stream.length_left() != 0:
					raise ValueError(f"Unexpected end of tag data in the middle of a layout of type \"{layout.definition.unique_id}\"!")  from eof
		else:
			fields_data = self._parse_fields(element_stream, field_set_def.merged_fields, is_array=False)
		layout.add_missing_fields(fields_data)
		return _TagFieldElement(tuple(fields_data), 
                         field_set_def.auto_c_name_to_field_index,
                         field_set_def.auto_pascal_name_to_field_index)
 
	def _setup_tag_readers(self):
		endianness = self.endianness
		readers = _TagReaderCache.get(endianness, self.is_big_endian)
		# primitve type structures
		s_ulong = readers.s_ulong
		if self._fast_tag_loaders:
			self.s_ulong = s_ulong
			self.s_short = readers.s_short
			self.s_ushort = readers.s_ushort
			self.s_char = readers.s_char
			self.s_uchar = readers.s_uchar
			self.s_2short = readers.s_2short
			self.s_2real = readers.s_2real
			self.s_3real = readers.s_3real
			self.s_4real = readers.s_4real
			self.s_real = readers.s_real
			self.s_long = readers.s_long
  
		# tag reference (editor) layout:
		# tag: cc4, tag type
		# path_pointer: u4, is invalid/garbage on disk
		# path_length: u4
		# tag_index: u4, is invalid/garbage on disk
		s_tag_reference = readers.s_tag_reference
		# tag block (editor) layout:
		# count: u4
		# elements: void* # invalid/garbage on disk
		# defintion: void* # invalid/garbage on disk
		s_tag_block = readers.s_tag_block
  
		read_ulong_integer = readers.read_ulong_integer
		read_cc4 = readers.read_cc4
		read_real = readers.read_real
		read_uchar_integer = readers.read_uchar_integer
		read_ushort_integer = readers.read_ushort_integer
		read_two_reals = readers.read_two_reals
		read_three_reals = readers.read_three_reals
		read_four_reals = readers.read_four_reals


		def string_id_to_str(string_id):
			# decode string ID (lenght + numberical ID)
			length = (string_id >> 24) & 0xFF
			#identifier = string_id & (0xFF << 24) # unused
			# read from the tag stream not element stream!
			value = self._read_str(length)
			return value
		
		def read_string_id(es: _ByteStream) -> str:
			string_id = read_ulong_integer(es)
			return string_id_to_str(string_id)

		def read_tag_reference(es: _ByteStream):
			# read structure in element stream
			tag_group = read_cc4(es)
			try:
				path_length, = s_tag_reference.unpack(es.read(12))
			except _ByteStream.EOF as eof:
				# rethrow it so that the caller knows something went wrong
				# this is required as es.length_left() could be equal to zero at this point
				# which would indicate an early (but valid!) end to the stream
				# but we are actually in the middle of reading a field
				raise ValueError("Unexpected end of stream while reading tag reference! Original error:" +  str(eof))
			
			tag_path = self._read_str(path_length, null_terminated=True) # tag stream!
			return _TagReference(tag_group, tag_path)

		def read_data_field(es: _ByteStream):
			# tag data field:
			# size: u4
			# stream_flags: u4
			# stream_offset: u4
			# data_ptr: u4
			# definition_ptr: u4
			size, = s_ulong.unpack(es.read(4))
			try:
				es.skip(16)
			except _ByteStream.EOF as eof:
				# same reasoning as above
				raise ValueError("Unexpected end of stream while reading data field! Original error:" +  str(eof))
			# read data from tag stream
			value = self._stream.read(size)
			if len(value) != size:
				raise ValueError("Unexpected end of stream while reading the contents of a data field!")
			return value

		self._tag_readers = {
			"String" : lambda es: es.read_string(0x20),
			"LongString": lambda es: es.read_string(0x100),
			"CharInteger": readers.read_char_integer,
			"ShortInteger": readers.read_short_integer,
			"LongInteger": readers.read_long_integer,
			"Angle": read_real,
			"Real": read_real,
			"RealFraction": read_real,
			"StringId": read_string_id,
			"OldStringId":  (lambda es: es.read_string(0x20)) if self._header.old_string_id_format else read_string_id,
			"Tag": read_cc4,

			# enums and flags are treated as unsigned
			"CharEnum": read_uchar_integer,
			"ByteFlags": read_uchar_integer,
			"ByteBlockFlags": read_uchar_integer,
			"ShortEnum": read_ushort_integer,
			"WordFlags": read_ushort_integer,
			"WordBlockFlags": read_ushort_integer,
			"LongEnum": read_ulong_integer,
			"LongFlags": read_ulong_integer,
			"LongBlockFlags": read_ulong_integer,

			"Point2D": readers.read_point2d,
			"Rectangle2D": readers.read_rect,
			"RgbColor": read_ulong_integer,
			"ArgbColor": read_ulong_integer,
			"RealPoint2D": read_two_reals,
			"RealVector2D": read_two_reals,
			"RealBounds": read_two_reals,
			"RealFractionBounds": read_two_reals,
			"AngleBounds": read_two_reals,
			"RealEulerAngles2D": lambda es: _EulerAngles2D(*read_two_reals(es)),

			"RealPoint3D": read_three_reals,
			"RealVector3D": read_three_reals,
			"RealRgbColor": read_three_reals,
			"RealHsvColor": read_three_reals,
			"RealQuaternion": read_four_reals,
			"RealArgbColor": read_four_reals,
			"RealAhsvColor": read_four_reals,

			"RealEulerAngles3D": lambda es: _EulerAngles3D(*read_three_reals(es)),
			"RealPlane2D": lambda es: _RealPlane2D(*read_three_reals(es)),
			"RealPlane3D": lambda es: _RealPlane3D(*read_four_reals(es)),

			"ShortBounds": readers.read_two_shorts,

			"TagReference": read_tag_reference,

     
			"CharBlockIndex": read_uchar_integer,
			"CustomCharBlockIndex": read_uchar_integer,

			"ShortBlockIndex": read_ushort_integer,
			"CustomShortBlockIndex": read_ushort_integer,

			"LongBlockIndex": read_ulong_integer,
			"CustomLongBlockIndex": read_ulong_integer,
   
			"Data": read_data_field,

			"VertexBuffer": lambda es: bytes(es.read(0x20)),
			"Ptr": lambda es: bytes(es.read(self.pointer_size)),

			"Explanation": lambda _: None,
			"Custom": lambda _: None,
		}
  
		def read_block_field(es: _ByteStream, field_def: FIELD_TYPE):
			count, elements_ptr, defintion_ptr = s_tag_block.unpack(es.read(12))
			if count != 0: # lots of tag stream reads!!
				return self._read_tag_block(field_def.layout, count)
			else:
				return None
		cast = _typing.cast
		def read_array_field(es: _ByteStream, field_def: FIELD_TYPE):
			if es.length_left() == 0:
				return None
			array_entries = []
			array_def = cast(_FieldArrayDef, field_def)
			for _ in range(array_def.count):
				array_entries.append(tuple(self._parse_fields(es, array_def.entry_fields, is_array=True)))
			return tuple(array_entries)

		def read_struct_field(es: _ByteStream, field_def: FIELD_TYPE):
			struct_layout, s_count = self._read_field_set_header(field_def.layout, self.FieldSetTypes.TagStructFieldData)
			if s_count != 1 and s_count is not None:
				raise ValueError(f"Expected a single block for structure, got {s_count}")

			struct_data_buffer = es.read(min(struct_layout.element_size, es.length_left()))
			struct_stream = _ByteStream(struct_data_buffer)
   
			value = self._read_struct_data(struct_layout, struct_stream)
			assert struct_stream.length_left() == 0, "Data left over after reading struct!"
   
			return value

		read_pad_field = readers.read_pad_field
	
		self._tag_readers_special_field = {
			"Block": read_block_field,
			"Array": read_array_field,
			"Pad": read_pad_field,
			"Skip": read_pad_field,
			"UselessPad": read_pad_field if self._header.include_useless_padding else (lambda es, def_: None),
			"Struct": read_struct_field,
		}

   
	def _parse_fields(self, element_stream: _ByteStream, fields: FIELDS_TYPE, is_array: bool = False):
		fields_data: list[_TagField] = []
		# we use two lookup tables because passing the definition to all readers
		# actually slows down parsing a little bit
		READERS = self._tag_readers
		SPECIAL_READERS = self._tag_readers_special_field
  
		for field_def in fields:
			type_name = field_def.type
			reader = READERS.get(type_name, None)
			try:
				if reader is not None:
					value = reader(element_stream)
				else:
					reader = SPECIAL_READERS.get(type_name, None)
					if reader is None:
						raise RuntimeError(f"Unexpected/unsupported field type: \"{type_name}\" (check your defintions)")
					value = reader(element_stream, field_def)
			except _ByteStream.EOF as eof:
				# check if the stream ended at a field boundry
				# if it did this could be a valid truncated tag created by implicit versioning (append)
				# if not we either read the tag wrong or it's most likely corrupt
				if element_stream.length_left() != 0:
					raise ValueError(f"Unexpected end of tag data in the middle of a field of type \"{type_name}\"!")  from eof
				elif is_array:
					raise ValueError("Unexpected early end of tag data inside an array/inlined-struct!")  from eof
			field = _TagField(field_def, value)
			fields_data.append(field)
   
		return fields_data

			
	def read_cc4(self):
		read = self._stream.read(4)
		if not self._header.is_big_endian:
			read = read[::-1]
		return read.decode()

	def _read(self, length: int):
		assert length != -1
		data = self._stream.read(length)
		if len(data) != length:
			raise ValueError("Unexpected end of tag!")
		return data
	def _read_str(self, length: int, null_terminated: bool = False):
		if length == 0:
			return ""
		# this function would be so much cleaner if someone didn't include a trailing null
		# in path names
		if null_terminated:
			length += 1
		data = self._read(length)
		if null_terminated:
			if data[-1] != 0:
				raise ValueError("String expected to be null terminated but wasn't!")
			data = data[:-1]
		return data.decode(errors="surrogateescape")
  
	@property
	def endianness(self):
		return ">" if self._header.is_big_endian else "<"
	
	@property
	def is_big_endian(self):
		return self._header.is_big_endian

	@property
	def pointer_size(self):
		return 4
     

class TagLoader:
	__slots__ = ("_definitions", "_tag_group_mapping", "_defs_version")
	def __init__(self, definitions: _Definitions):
		self._definitions: _Definitions = definitions
		self._tag_group_mapping = definitions.TagGroups
		self._defs_version = definitions.version_hash

	def load_tag(self, path: str):
		with open(path, 'rb') as f:
			state = _TagLoadingState(self._tag_group_mapping, f, self._defs_version)
			return state.read()