## Copyright 2024 <num0005@outlook.com>, some rights reserved
##
## This file is part of the Pytolith project licensed under the terms of the MIT license, see COPYING for more details
## This notice must be retained in all copies of this file

import os as _os
import pathlib as _pathlib

from Pytolith.Definitions import Definitions as _defintions
from Pytolith._TagLoader.Loader import TagLoader as _loader

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

class TagSystem():
	def __init__(self, tag_definitions: _defintions = None, tag_folder: str|None = None):
		if tag_definitions is None:
			tag_definitions = _get_default_definitions()
		self.tag_definitions = tag_definitions
		self._loader = _loader(self.tag_definitions)
		self.tag_folder = tag_folder

	def load_tag_from_path(self, file_path: str):
		return self._loader.load_tag(file_path)

	def load_tag(self, tag_path: str):
		if self.tag_folder is None:
			raise ValueError("Cannot use load_tag if the tag folder is not set, did you mean to use load_tag_from_path?")
		file_path = _os.path.join(self.tag_folder, tag_path)
		return self.load_tag_from_path(file_path)