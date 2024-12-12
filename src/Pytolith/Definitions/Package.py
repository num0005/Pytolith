from __future__ import annotations as _

from dataclasses import asdict as _asdict

import os as _os
import collections.abc as _abc

import Pytolith.Definitions.Fields as _Fields
import Pytolith.Definitions.Layout as _Layout

import xml.etree.ElementTree as _ET

import pickle as _pickle
import zlib as _zlib
	

class Definitions:
	def __init__(self):
		self.TagGroups: dict[str, _Layout.TagGroup] = dict()

		self._is_loaded = False
		self._id_to_layout: dict[str, _Layout.LayoutDef] = dict()
		self._id_to_options: dict[str, _Fields.TagOptions] = dict()
  
  
	@property
	def is_loaded(self):
		"""Are the tag defintions loaded?"""
		return self._is_loaded

	def load_from_xml(self, folder: str):
		assert not self._is_loaded, "Defintions are already loaded!"
		self._id_to_element: dict[str, _ET.Element] = dict()
		self._id_to_source_xml: dict[str, str] = dict()
		self._xml_load_path = folder

		# stage 0: load the xml for all files + parse it to get all tag layouts
		# and top level tag groups
  
		def is_xml_file(path: str):
			return  _os.path.isfile(path) and path.endswith(".xml")

		for file in _os.listdir(_os.path.join(folder, "common")):
			path = _os.path.join(folder, "common", file)
			if is_xml_file(path):
				self._load_file(_os.path.join(folder, "common", file))

		files_with_groups: list[tuple[str, _ET.Element]] = []
		for file in _os.listdir(folder):
			path = _os.path.join(folder, file)
			if not is_xml_file(path):
				continue
			relative_path = _os.path.relpath(path, folder)
			files_with_groups.append((relative_path, self._load_file(path)))

		# stage 1: parse all layouts including references
		for id, layout_element in self._id_to_element.items():
			self._parse_layout_from_xml(id, layout_element)

		# stage 2: resolve tag groups
		for filename, group_element in files_with_groups:
			tag_group = self._parse_group_from_xml(group_element, filename)
			self.TagGroups[tag_group.group] = tag_group
   
		# stage 3: merge parents
		for group in self.TagGroups.values():
			if group.parent:
				self._merge_fields_with_parent(group)
		# stage 3b: explictly set the other layouts to not have merged fields
		for layout in self._id_to_layout.values():
			for field_set in layout.versions:
				if not field_set._loader_merge_fields_set():
					field_set._loader_set_merged_fields(False)

		
		del self._id_to_element
		del self._id_to_source_xml

		self._is_loaded = True
  
	def dumps(self):
		"""Pickle and compress the definitions data"""
		import pickletools
  
		pickled_string = _pickle.dumps(self)
		pickled_string = pickletools.optimize(pickled_string)
		return _zlib.compress(pickled_string, level=9)

	@staticmethod
	def loads(compressed: '_abc.Buffer'):
		"""Loads definitions dumped using `definitions.dump()`"""
		pickled = _zlib.decompress(compressed)
		data = _pickle.loads(pickled)
		assert type(data) == Definitions
		return data
	
	@staticmethod
	def load(file_name: str):
		with open(file_name, "rb") as f:
			contents = f.read()
			return Definitions.loads(contents)

	def _merge_fields_with_parent(self, group: _Layout.TagGroup):
		# check if merging has already handled for this layout
		if all(fieldset._loader_merge_fields_set() for fieldset in group.layout.versions):
			return False
  
		if group.parent is None:
			# no parent, set the merged fields to be None
			for fieldset in group.layout.versions:
				fieldset._loader_set_merged_fields(False)
			return False

		parent_layout = self.TagGroups[group.parent].layout

		self._merge_fields_with_parent(self.TagGroups[group.parent]) # merge parent fields first

		for field_set in group.layout.versions:
			assert field_set.parent_version is not None, f"tag {group.name}/{group.group} uses inheritence but parent version is not set for layout {field_set.version}!"
			parent_field_set = parent_layout.versions[field_set.parent_version]
			# merge with parent
			field_set._loader_set_merged_fields(parent_field_set.merged_fields + field_set.fields)
	
	def _load_file(self, filename: str) -> _ET.Element:
		document = _ET.parse(filename)
		relative_path = _os.path.relpath(filename, self._xml_load_path)
		# note and extract all the layouts in the file
		for layout in document.iter("Layout"):
			id = layout.attrib["regolithID"]
			if id in self._id_to_element:
				raise RuntimeError(f"Duplicate layout declaration for {id}, please fix this in tag defs!")

			self._id_to_element[id] = layout
			self._id_to_source_xml[id] = relative_path
		# we can actually parse the enum defintions already
		for option in document.iter("Options"):
			id = option.attrib["regolithID"]
			c_style_name = option.get("CStyleName")
			pascal_case_name = option.get("pascalStyleName")

			entries = self._parse_options_data(option)
   
			if id in self._id_to_options:
				
				raise RuntimeError(f"Duplicate options declaration for {id}! Please fix this in tag defintions!")

			self._id_to_options[id] = _Fields.TagOptions(id, 
                                                c_style_name=c_style_name, 
                                                pascal_style_name=pascal_case_name, 
                                                entries=entries,
                                                source_xml_file=relative_path)
		
		return document.getroot()
	
	def _parse_group_from_xml(self, element: _ET.Element, source_file: str):
		assert element.tag == "TagGroup"

		group = element.attrib["group"]
		parent = element.attrib.get("parent", None)
		name = element.attrib["name"]
		version = int(element.attrib["version"])

		definition = self._get_layout_for_element("tag group", element)
		
		return _Layout.TagGroup(group, name, parent, version, definition, source_file)
	
	def _get_layout_by_id(self, id: str):
		return self._parse_layout_from_xml(id, self._id_to_element[id])
	
	def _parse_layout_from_xml(self, id: str, element: _ET.Element):
		assert element.tag == "Layout"
		assert element.attrib["regolithID"] == id

		if id in self._id_to_layout.keys():
			return self._id_to_layout[id]

		internal_name: str = element.attrib["internalName"]
		display_name = element.attrib.get("name")
		structure_tag = element.attrib.get("tag")
		is_structure = structure_tag is not None
  
		source_xml_file = self._id_to_source_xml[id]

		# we need to make sure to create the layout now
		# and add it to the internal map now before parsing the fields
		# so we can parse circular references in one shot instead of two

		layout = _Layout.LayoutDef(id, internal_name, display_name, is_structure, structure_tag, source_xml_file)
		self._id_to_layout[id] = layout
		versions: list[_Layout.FieldSetDef] = []

		# parse all the field-set versions
		for fieldset_index in range(len(element)):
			fs_elem = element[fieldset_index]

			fs_version = int(fs_elem.attrib["version"])
			sizeof_val = int(fs_elem.attrib["sizeofValue"])
			sizeof_source = fs_elem.attrib.get("tag")

			assert fs_version == fieldset_index or id == "block:vertex_shader"

			fields: list[_Fields.FieldDef] = []
			alignment: None|int = None
			sizeof_override: None|int = None
			parent_version: None|int = None


			if "alignment" in fs_elem.attrib.keys():
				alignment = int(fs_elem.attrib["alignment"])
			if "sizeofOverride" in fs_elem.attrib.keys():
				sizeof_override = int(fs_elem.attrib["sizeofOverride"])
			if "parentVersion" in fs_elem.attrib.keys():
				parent_version = int(fs_elem.attrib["parentVersion"])

			for field_elem in fs_elem:
				fields.append(self._parse_field(field_elem))

			fs = _Layout.FieldSetDef(fs_version, sizeof_val, alignment, parent_version, sizeof_override, tuple(fields), sizeof_source)

			versions.append(fs)
		
		# bypass frozen
		object.__setattr__(layout, "versions", tuple(versions))
		return layout
	
	def _parse_field_name(self, element: _ET.Element) -> _Fields.FieldNameInfo:
		name = element.get("name")
		description = element.get("description")
		units = element.get("units")

		is_block_name_source = element.get("blockNameSource") == "true"
		is_readonly = element.get("readOnly") == "true"
		is_expert = element.get("expertOnly") == "true"

		c_style_name = element.get("CStyleName")
		pascal_case_name = element.get("pascalStyleName")

		return _Fields.FieldNameInfo(name, description, units, is_block_name_source, is_readonly, is_expert, c_style_name, pascal_case_name)
	
	def _get_layout_for_element(self, usecase: str, field_elem: _ET.Element):
		assert len(field_elem) == 1, f"{usecase} should have exactly one child element (the layout)"
		match field_elem[0].tag:
			case "Layout":
				defintion = self._parse_layout_from_xml(field_elem[0].get("regolithID"), field_elem[0])
			case "LayoutXRef":
				defintion = self._get_layout_by_id(field_elem[0].text)
			case _:
				raise ValueError(f"Invalid tag layout declaration, wrong xml tag {field_elem[0].tag}")
		return defintion

	
	def _parse_field(self, field_elem: _ET.Element) -> _Fields.FieldDef:
		field_type: str = field_elem.tag
		name: _Fields.FieldNameInfo = self._parse_field_name(field_elem)
		tag: str = field_elem.get("tag")
		block_reference_id: str = field_elem.get("blockReference")

		base_field_def = _Fields.FieldDef(**_asdict(name), type=field_type, tag=tag, block_index_definition_reference_id=block_reference_id)
		field_def = base_field_def
		

		match field_type:
			case "Pad"|"UselessPad"|"Skip":
				length = int(field_elem.attrib["length"])
				sizeof_source = field_elem.get("sizeOfSource")
				field_def = _Fields.FieldPadDef(**_asdict(base_field_def), length=length, size_of_source=sizeof_source)
			case "CharEnum"|"ShortEnum"|"LongEnum"|"Enum"|"ByteFlags"|"WordFlags"|"LongFlags":
				entries_anon = None
				options_obj = None

				if field_elem[0].tag == "Options":
					options_obj = self._id_to_options[field_elem[0].attrib["regolithID"]]
				elif field_elem[0].tag == "OptionsXRef":
					options_obj = self._id_to_options[field_elem[0].text]
				else:
					entries_anon = self._parse_options_data(field_elem)
     
				assert (entries_anon is None) != (options_obj is None)
 
				field_def = _Fields.FieldWithOptionsDef(**_asdict(base_field_def), _entries_anon = entries_anon, options=options_obj)
			case "TagReference":
				allowed_tag_groups: list[str] = []
				for tag_elem in field_elem:
					allowed_tag_groups.append(tag_elem.text)
				field_def = _Fields.FieldTagReferenceDef(*_asdict(base_field_def).values(), tuple(allowed_tag_groups))
			case "Struct":
				definition = self._get_layout_for_element("structure", field_elem)
				field_def = _Fields.FieldStructureDef(**_asdict(base_field_def), layout=definition)
			case "Block":
				definition = self._get_layout_for_element("tag block", field_elem)
				max_element_count = int(field_elem.get("maxElementCount"))
				max_element_count_source = field_elem.get("maxElementCountSource")
				field_def = _Fields.FieldBlockDef(**_asdict(base_field_def), layout=definition, max_element_count=max_element_count, max_element_count_source=max_element_count_source)
			case "Array":
				count = int(field_elem.attrib["count"])
				fields: list[_Fields.FieldDef] = []
				for child in field_elem:
					fields.append(self._parse_field(child))
				field_def = _Fields.FieldArrayDef(**_asdict(base_field_def), count=count, entry_fields=tuple(fields))


		return field_def

	def _parse_options_data(self, options_elem: _ET.Element):	
		options: list[_Fields.FieldNameInfo] = []
		for option_elem in options_elem:
			options.append(self._parse_field_name(option_elem))
		return tuple(options)