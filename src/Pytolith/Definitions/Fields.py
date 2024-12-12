from __future__ import annotations as _
from dataclasses import dataclass as _dataclass, field as _field

@_dataclass(frozen=True, slots=True)
class FieldNameInfo:
	name: str|None
	description: str|None
	units: str|None

	# flags for visual tag editor (e.g. Guerilla, Assembly, Regolith, etc )
	is_block_name_source: bool # should the block element name be set using this field?
	is_readonly: bool
	is_expert: bool

	# for generating structures/classes in different languages
	c_style_name: str
	pascal_style_name: str

@_dataclass(frozen=True, slots=True)
class TagOptions:
	unique_id: str
	"""regolith ID"""
	# for generating structures/classes in different languages
	c_style_name: str
	pascal_style_name: str
 
	source_xml_file: str
	"""What XML was this Options object defined in?"""
 
	entries: tuple[FieldNameInfo] = _field(default_factory=tuple)

@_dataclass(frozen=True, slots=True)
class FieldDef(FieldNameInfo):
	type: str
	tag: str

	block_index_definition_reference_id: str|None
	"""tag block index fields only"""

@_dataclass(frozen=True, slots=True)
class FieldPadDef(FieldDef):
	# length of the field
	length: int
	# debugging only
	size_of_source: str

@_dataclass(frozen=True, slots=True)
class FieldWithOptionsDef(FieldDef):
	options: TagOptions|None
	"""Options object for this field, None if the enum is anonymous. You can access the entries directly using `entries` if you are just inspecting the field."""
 
	_entries_anon: tuple[FieldNameInfo]|None = None
 
	@property
	def entries(self):
		"""flags or enums for this field"""
		return self.options.entries if self.options else self._entries_anon

	@property
	def unique_id(self):
		"""Unique regolith ID or None if enum is anonymous."""
		return self.options.unique_id if self.options else None

@_dataclass(frozen=True, slots=True)
class FieldTagReferenceDef(FieldDef):
	allowed_tag_types: tuple[str] = _field(default_factory=tuple)

@_dataclass(frozen=True, slots=True)
class FieldArrayDef(FieldDef):
	# number of entries
	count: int
	entry_fields: tuple[FieldDef] = _field(default_factory=tuple)

@_dataclass(frozen=True, slots=True)
class FieldStructureDef(FieldDef):
	layout: _LayoutDef

@_dataclass(frozen=True, slots=True)
class FieldBlockDef(FieldDef):
	layout: _LayoutDef
	max_element_count: int
	# debug only
	max_element_count_source: str|None = None

from Pytolith.Definitions.Layout import LayoutDef as _LayoutDef