from __future__ import annotations as _

from dataclasses import dataclass as _dataclass
import Pytolith.Definitions as _Defs

@_dataclass(slots=True)
class Rectangle2D:
	x0: int = 0
	y0: int = 0
	x1: int = 0
	y1: int = 0
 
@_dataclass(slots=True)
class Point2D:
	x: int = 0
	y: int = 0

@_dataclass(slots=True)
class EulerAngles2D:
	yaw: float = 0.0
	pitch: float = 0.0

@_dataclass(slots=True)
class EulerAngles3D:
	yaw: float = 0.0
	pitch: float = 0.0
	roll: float = 0.0

@_dataclass(slots=True)
class RealPlane2D:
	x: float = 0.0
	y: float = 0.0
	distance: float = 0.0

@_dataclass(slots=True)
class RealPlane3D:
	x: float = 0.0
	y: float = 0.0
	z: float = 0.0
	distance: float = 0.0
 
@_dataclass(slots=True)
class TagReference:
	group: str
	path: str

#
# Simple scalar values not related to the tag system
#

TAG_FIELD_BASIC_VALUES = str|int|float|bytes
TAG_FIELD_COLOR_VALYES = tuple[float]|int # float tuple colors + int for integer colors

TAG_FIELD_POINT_VALUES = Point2D|tuple[float] # point2d type for integer 2d points + float tuples for real 2d/3d points and vectors
TAG_FIELD_GEO_VALUES = TAG_FIELD_POINT_VALUES|EulerAngles2D|EulerAngles3D|RealPlane2D|RealPlane3D

TAG_FIELD_SCALAR_VALUES = TAG_FIELD_BASIC_VALUES|TAG_FIELD_COLOR_VALYES|TAG_FIELD_GEO_VALUES

#
# Values relating to the tag system
#
TAG_FIELD_ARRAY_VALUE = tuple[tuple["TagField"]] # tuple of array entries, which themselves are tuples of fields
 
@_dataclass(frozen=False, slots=True)
class TagField:
	defintion: _Defs.FieldDef|_Defs.FieldPadDef|_Defs.FieldWithOptionsDef|_Defs.FieldTagReferenceDef|_Defs.FieldStructureDef|_Defs.FieldBlockDef
	value: TAG_FIELD_ARRAY_VALUE|TAG_FIELD_SCALAR_VALUES|TagReference|TagBlock|TagStruct

@_dataclass(slots=True, frozen=True)
class TagLayoutConfig:
     
	definition: _Defs.LayoutDef
	version: int
	element_size: int
	fieldset_defintion: _Defs.FieldSetDef = None
	is_version_valid: bool = False
 
	def __post_init__(self):
		is_version_valid = self.version >= 0 and self.version < len(self.definition.versions)
		if is_version_valid:
			fieldset_defintion = self.definition.versions[self.version]
			object.__setattr__(self, "fieldset_defintion", fieldset_defintion)
		object.__setattr__(self, "is_version_valid", is_version_valid)

	def add_missing_fields(self, data: list[TagField]):
		"""Add in missing fields (but doesn't fill the data in)"""
		fields_def = self.fieldset_defintion.merged_fields
		for i in range(len(data), len(fields_def)):
			defintion = fields_def[i]
			data.append(TagField(defintion, None))

class TagFieldElement():
	"""Wrapper around a tuple of tag fields, allows accessing fields by their snake_case or PascalCase names not just their index"""
	__slots__ = ("pytolith_fields", "c_name_mapping", "pascal_name_mapping")
	def __init__(self, fields, c_name_mapping: dict[str, int], pascal_name_mapping: dict[str, int]):
		self.pytolith_fields: tuple[TagField] = fields
		self.c_name_mapping = c_name_mapping
		self.pascal_name_mapping = pascal_name_mapping
 
	def __len__(self):
		return len(self.pytolith_fields)
	def __repr__(self):
		return repr(self.pytolith_fields)
	def __iter__(self):
		return self.pytolith_fields.__iter__()
	def __getitem__(self, key):
		if isinstance(key, str):
			return self.get_by_name(key)
		return self.pytolith_fields[key]
	def __getattr__(self, name):
		return self.get_by_name(name)
	def __dir__(self):
		return set(dir(type(self)) + list(self.__slots__)) | set(self.c_name_mapping.keys()) | self.pascal_name_mapping.keys()

	def get_by_name(self, name: str):
		"""Lookup a field by name, raises an index error if it doesn't exist"""
		index = self.c_name_mapping.get(name, None)
		if not index:
			index = self.pascal_name_mapping.get(name, None)
		if not index:
			raise IndexError(f"No such field name: {name}")
		return self.pytolith_fields[index]

	def get_by_c_name(self, name: str):
		"""Lookup a field by c-style name (snake_case), raises an index error  if it doesn't exist"""
		index = self.c_name_mapping.get(name, None)
		if not index:
			raise IndexError(f"No such field c_name: {name}")
		return self.pytolith_fields[index]

	def get_by_pascal_name(self, name: str):
		"""Lookup a field by PascalCase name, raises an index error if it doesn't exist"""
		index = self.c_name_mapping.get(name, None)
		if not index:
			raise IndexError(f"No such field PascalName: {name}")
		return self.pytolith_fields[index]

@_dataclass(frozen=False, slots=True)
class TagBlock():
	layout: TagLayoutConfig
	elements: list[TagFieldElement]

	def add_element(self):
		if self.defintion.max_element_count == len(self.elements):
			raise ValueError("Too many tag elements!")

		new_element_data = []
		self.layout.add_missing_fields(new_element_data)
		self.elements.append(tuple(new_element_data))

@_dataclass(frozen=False, slots=True)
class TagStruct():
	layout: TagLayoutConfig
	fields: TagFieldElement

@_dataclass(frozen=False, slots=True)
class TagGroupData:
	_root_block: TagBlock
	definition: _Defs.TagGroup
 
	@property
	def fields(self):
		"""Tuple containing all fields for this tag"""
		return self._root_block.elements[0]
	@property
	def layout(self):
		"""Versioned tag layout defintion for this tag"""
		return self._root_block.layout