## Copyright 2024 <num0005@outlook.com>, some rights reserved
##
## This file is part of the Pytolith project licensed under the terms of the MIT license, see COPYING for more details
## This notice must be retained in all copies of this file

from __future__ import annotations as _
from dataclasses import dataclass as _dataclass, field as _field
import os as _os
import pathlib as _pathlib

from Pytolith.Definitions import Definitions as _defintions
from Pytolith.TagTypes import TagReference as _TagReference
from Pytolith._TagBinary.Loader import TagLoader as _loader

from Pytolith._TagBinary.Header import Header as _Header

@_dataclass
class TagReferenceDatabase():
     depends_on: dict[_TagReference, set[_TagReference]] = _field(default_factory=dict)
     """Mapping from a tag to all tags that it depends on, avoid modifying this value directly as it needs to be kept in sync with `depeneded_on_by`"""
     
     depeneded_on_by: dict[_TagReference, set[_TagReference]] = _field(default_factory=dict)
     """Mapping from a tag to all tags that depend on it, avoid modifying this value directly as it needs to be kept in sync with `depends_on`"""
     
     tag_version_info: dict[_TagReference, tuple[int, int, str]] = _field(default_factory=dict)
     """Version information for cached tags, (checksum, data_size, engine_tag)"""
     
     def _set_tag_dependenices(self, tag: _TagReference, tag_depends_on: list[_TagReference]):
          
          tag_depends_on = set(t for t in tag_depends_on if t.path != "" and t.group != None)
          old_tag_depends_on = self.depends_on.get(tag, None)
          if old_tag_depends_on is None:
               self.depends_on[tag] = tag_depends_on
               for other_tag in tag_depends_on:
                    self._add_tag_depended_by(other_tag, tag)
          new_depends_on = tag_depends_on - old_tag_depends_on
          removed_depends_on = old_tag_depends_on - tag_depends_on
          # add new depends
          for other_tag in new_depends_on:
               self._add_tag_depended_by(other_tag, tag)
          # remove old ones
          for other_tag in removed_depends_on:
               self.depeneded_on_by[other_tag].remove(tag)
           
     def _add_tag_depended_by(self, tag: _TagReference, other_tag: _TagReference):
          try:
               depended_on = self.depeneded_on_by[tag]
          except:
               depended_on = set()
               self.depeneded_on_by[tag] = depended_on
          depended_on.add(other_tag)
          
     def remove_tag(self, tag: _TagReference):
          self._set_tag_dependenices(tag, [])
          self.tag_version_info[tag] = None
          
     def need_to_update_tag(self, header: _Header, tag: _TagReference):
          new_version = self._get_version_from_header(header)
          return self.tag_version_info.get(tag, None) != new_version
     
     @staticmethod
     def _get_version_from_header(header: _Header):
          return (header.checksum, header.data_size, header.engine_tag)
          
     def set_tag_data(self, header: _Header, tag: _TagReference, tag_depends_on: list[_TagReference]):
          version = self._get_version_from_header(header)
          self._set_tag_dependenices(tag, tag_depends_on)
          self.tag_version_info[tag] = version

def _load_default_definitions():
     HALO2_PATH = _pathlib.Path("Data")/"TagLayouts"/"Halo2"
     current_file_dir = _pathlib.Path(_os.path.abspath(__file__)).parent
     root_directory = current_file_dir.parents[1]
     
     # load XML layouts if those exist, otherwise load pickled file
     xml_layouts_path = (root_directory/HALO2_PATH)
     pickled_path = (current_file_dir/"halo2.layouts")
     if _os.path.exists(xml_layouts_path) and _os.path.isdir(xml_layouts_path):
          defs = _defintions()
          defs.load_from_xml(xml_layouts_path)
          return defs
     else:
          return _defintions.load(pickled_path)

__default_defs_cache = None
def _get_default_definitions():
     global __default_defs_cache
     if __default_defs_cache is None:
          __default_defs_cache = _load_default_definitions()
     return __default_defs_cache


#type TAG_FILE_TREE = dict[str, None|TAG_FILE_TREE]
TAG_FILE_TREE = dict[str, None]

class TagSystem():
     def __init__(self, tag_folder: str|_pathlib.Path, tag_definitions: _defintions|None = None):
          if tag_definitions is None:
               tag_definitions = _get_default_definitions()
          self.tag_definitions = tag_definitions
          self._loader = _loader(self.tag_definitions)
          self.tag_folder = _pathlib.Path(tag_folder)
     
     def _get_list_of_tags_os(self):
          tag_extensions = ["."+definition.name for definition in self.tag_definitions.TagGroups.values()]
          tag_file_names = []
          for subdir, dirs, files in _os.walk(self.tag_folder):
               subdir = _pathlib.Path(subdir)
               for file in files:
                    filepath = subdir/file
                    if filepath.suffix in tag_extensions:
                         filepath = filepath.relative_to(self.tag_folder)
                         tag_file_names.append(filepath)
          return tag_file_names
     
     def get_list_of_tags(self):
          return [_pathlib.PureWindowsPath(p) for p in self._get_list_of_tags_os()]
     
     @staticmethod 
     def _convert_tag_list_to_tree(tag_list: list[_pathlib.PureWindowsPath]):
          root: TAG_FILE_TREE = dict()
          def process(directory: TAG_FILE_TREE, parts: tuple[str]):
               assert len(parts) >= 1
               if len(parts) == 1:
                    directory[parts[0]] = None
               else:
                    try:
                         subdir = directory[parts[0]]
                    except:
                         subdir = dict()
                         directory[parts[0]] = subdir
                    process(subdir, parts[1:])
          for tag in tag_list:
               process(root, tag.parts)
          return root
     
     def get_tag_tree(self):
          return self._convert_tag_list_to_tree(self.get_list_of_tags())
     
     def get_tag_references_for_tag_at_path(self, file_path: str):
          return self._loader.get_tag_references(file_path)

     def load_tag(self, tag_path: str|_pathlib.PurePath):
          if self.tag_folder is None:
               raise ValueError("Cannot use load_tag if the tag folder is not set, did you mean to use load_tag_from_path?")
          file_path = self.tag_folder/tag_path
          return self._loader.load_tag(str(file_path))