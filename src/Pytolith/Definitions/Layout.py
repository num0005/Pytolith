from __future__ import annotations as _

from dataclasses import dataclass as _dataclass, field as _field
from typing import ClassVar as _ClassVar, Literal as _Literal
import Pytolith.Definitions.Fields as _Fields

FIELD_TYPE = _Fields.FieldDef|_Fields.FieldPadDef|_Fields.FieldWithOptionsDef|_Fields.FieldTagReferenceDef
FIELDS_TYPE = tuple[FIELD_TYPE]

@_dataclass(frozen=True, slots=True)
class FieldSetDef:
	version: int
	"""Field set version."""
	sizeof_value: int
	"""`sizeof` the field set in the build the defintions are extracted from. Don't trust this value to be accurate, it is only provided as an aid when debugging."""

	alignment: int = 0

	parent_version: int|None = None
	"""If layout uses inheritance which version of the parent tag layout should we merge with?"""
	sizeof_override: int|None = None
	"""Override the legacy field lenght (length used when there is no tag field header)"""
 
 
	auto_c_name_to_field_index: dict[str, int] = _field(default_factory=dict, init=False, repr=False)
	"""Autogenerated c_name to field index mapping"""
	auto_pascal_name_to_field_index: dict[str, int]  = _field(default_factory=dict, init=False, repr=False)
	"""Autogenerated PascalName to field index mapping"""
 
	def __generate_mapping(self):
		self.auto_c_name_to_field_index.clear()
		self.auto_pascal_name_to_field_index.clear()
		merged_fields = self.merged_fields
		for i in range(len(merged_fields)):
			field = merged_fields[i]
			if field.c_style_name:
				assert field.c_style_name not in self.auto_c_name_to_field_index, f"duplicate C name in field set!"
				self.auto_c_name_to_field_index[field.c_style_name] = i
			if field.pascal_style_name:
				assert field.pascal_style_name not in self.auto_pascal_name_to_field_index, f"duplicate C name in field set!"
				self.auto_pascal_name_to_field_index[field.pascal_style_name] = i
				


	fields: FIELDS_TYPE = _field(default_factory=tuple)
	__merged_fields: FIELDS_TYPE|_Literal[False] = _field(default=None, init=False, repr=False) # backing store for merged fields
 
	@property
	def merged_fields(self):
		"""Returns the fields after accounting for any parent tags"""
		return self.__merged_fields if self.__merged_fields else self.fields

	__cached_field_partial: dict[str, int] = _field(default_factory=dict, init=False, repr=False)
	__cached_field_sizes: dict[tuple[bool,bool], int] = _field(default_factory=dict, init=False, repr=False)
 
	def sizeof_for_config(self, include_useless_pad: bool, use_old_string_id: bool):
		key = (include_useless_pad, use_old_string_id)
		if not key in self.__cached_field_sizes:
			length = self.__caclulate_size_for_config(include_useless_pad, use_old_string_id)
			for child_struct in self.child_structs:
				# messy messy messy
				# we are assuming here version 0 of any child structure is used
				# this seems like the least bad option when loading unversioned/size-free structures
				child_len = child_struct.layout.versions[0].sizeof_for_config(include_useless_pad, use_old_string_id)
				length += child_len
			self.__cached_field_sizes[key] = length
		return self.__cached_field_sizes[key]
	
	def __caclulate_size_for_config(self, include_useless_pad: bool, use_old_string_id: bool):
		partials = self.__caclulate_partials_length()
		# assume unpacked tags config
		base_length = (partials["base_length"] + partials["pointer_count"]*4 + partials["tag_data_count"]*20
                 	+ partials["tag_block_count"]*12 + partials["tag_reference_count"]*16
                    + partials["vertex_buffer_count"]*0x20)
		old_string_id_length = 32 if use_old_string_id else 4
		length = base_length + partials["old_string_id_count"]*old_string_id_length
		if include_useless_pad:
			length += partials["useless_pad_length"]
		return length

	@property
	def child_structs(self) -> list["FieldsWithLayouts.FieldStructureDef"]:
		partials = self.__caclulate_partials_length()
		return partials["structs"]

	FIELD_LENGTHS: _ClassVar = {
		"String" : 0x20,
		"LongString": 0x100,
		"StringId": 0x4,
		"CharInteger": 1,
		"ShortInteger": 2,
		"LongInteger": 4,
		"Angle": 4,
		"Real": 4,
		"RealFraction": 4,
		"Tag": 4,
		"CharEnum": 1,
		"ByteFlags": 1,
		"ByteBlockFlags": 1,
		"ShortEnum": 2,
		"WordFlags": 2,
		"WordBlockFlags": 2,
		"LongEnum": 4,
		"LongFlags": 4,
		"LongBlockFlags": 4,
		"Point2D": 4,
		"Rectangle2D": 4,
		"RgbColor": 4,
		"AgbColor": 4,
		"RealPoint2D": 8,
		"RealVector2D": 8,
		"RealBounds": 8,
		"RealFractionBounds": 8,
		"AngleBounds": 8,
		"RealPoint3D": 12,
		"RealVector3D": 12,
		"RealRgbColor": 12,
		"RealHsvColor": 12,
		"RealQuaternion": 16,
		"RealArgbColor": 16,
		"RealAhsvColor": 16,
		"RealEulerAngles2D": 8,
		"RealEulerAngles3D": 12,
		"RealPlane2D": 12,
		"RealPlane3D": 16,
		"ShortBounds": 4,
		"RealBounds": 8,
		"CharBlockIndex": 1,
		"CustomCharBlockIndex": 1,
		"ShortBlockIndex": 2,
		"CustomShortBlockIndex": 2,
		"LongBlockIndex": 4,
		"CustomLongBlockIndex": 4,
  
		"Explanation": 0,
		"Custom": 0
	}

	def __caclulate_partials_length(self):
		if len(self.__cached_field_partial) == 0:
			structs = []
			vertex_buffer_count = 0
			old_string_id_count = 0
			tag_reference_count = 0
			tag_block_count = 0
			tag_data_count = 0
			useless_pad_length = 0
			pointer_count = 0
			base_length = 0
   
			def calculate_fields_lengths(fields: FIELDS_TYPE, count: int):
				nonlocal  old_string_id_count
				nonlocal  tag_reference_count
				nonlocal  tag_block_count
				nonlocal  tag_data_count
				nonlocal  useless_pad_length
				nonlocal  pointer_count
				nonlocal  base_length
				nonlocal  vertex_buffer_count
				nonlocal  structs
				for field in fields:
					match field.type:
						case "OldStringId":
							old_string_id_count+=count
						case "TagReference":
							tag_reference_count+=count
						case "Block":
							tag_block_count+=count
						case "Data":
							tag_data_count+=count
						case "UselessPad":
							useless_pad_length+=field.length*count
						case "Pad"|"Skip":
							base_length+=field.length*count
						case "Ptr":
							pointer_count+=count
						case "VertexBuffer":
							vertex_buffer_count+=count
						case "Struct":
							structs += [field]*count
						case "Array":
							calculate_fields_lengths(field.entry_fields, field.count)
						case _:
							base_length += self.FIELD_LENGTHS[field.type]*count
								
			calculate_fields_lengths(self.merged_fields, 1)
			results = dict(locals())
			# delete things we don't want to return
			del results["self"]
			del results["calculate_fields_lengths"]
			self.__cached_field_partial.update(results)
		return self.__cached_field_partial

 
	def _loader_set_merged_fields(self, new_value):
		"""Internal setting for merged fields, can only be set once"""
		assert new_value is not None
  
		if self.__merged_fields is not None:
			raise RuntimeError("Attempting to set value of merged fields twice for field set, code outside of the definition loader should not attempt to modify this field")
		object.__setattr__(self, "_FieldSetDef__merged_fields", new_value) # bypass frozen
		# clear any lengths calculated since they are now invalid
		self.__cached_field_partial.clear()
		self.__cached_field_sizes.clear()
		# generate mappings
		self.__generate_mapping()
  
	def _loader_merge_fields_set(self):
		"""INTERNAL: Used by the loader to check if any required field merging operations are complete"""
		return self.__merged_fields is not None

	# only for debugging
	sizeof_source: str|None = None
	"""`sizeof` source string extracted from tag defintions. Using this for anything is highly not recommended"""


@_dataclass(frozen=True, slots=True)
class LayoutDef:
	unique_id: str
	"""Unique ID indentifying an `block:` or `struct:`"""
	internal_name: str
	"""Block/structure name extracted from the binary may be non-unique, `unique_id` if you need a unique name."""

	display_name: str|None
	"""Human readable name for the tag block if one is set"""

	is_structure: bool
	"""Is this a structure or is this a tag block?"""
	
	# structure-only field
	structure_tag: str|None = None
	"""Tag used for the tag field data header. Ignored for non-structure layouts.

 		(default value for tag blocks is 'tbfd', which might stand for "tag block field data")
  	"""

	source_xml_file: str = ""
	"""What XML was this Layout defined in?"""
   
	@property
	def tag_block_field_header_tag(self):
		value = self.structure_tag if self.is_structure else None
		if value is None:
			value = "tbfd" # matching toolkit behaviour here, which accepts the default header for structures
		return value

	versions: tuple[FieldSetDef] = _field(default_factory=tuple)

@_dataclass(frozen=True)
class TagGroup:
	group: str
	name: str
	parent: str|None
	version: int
	layout: LayoutDef
	source_xml_file: str
	"""What XML was this Tag Group defined in?"""