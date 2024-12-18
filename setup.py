## Copyright 2024 <num0005@outlook.com>, some rights reserved
##
## This file is part of the Pytolith project licensed under the terms of the MIT license, see COPYING for more details
## This notice must be retained in all copies of this file

# load unpacked library
import pathlib
import os
import sys

# load unpackage module
root_directory = pathlib.Path(os.path.abspath(__file__)).parent
sys.path.append(str(root_directory/"src"))
sys.path.append(str(root_directory))
import Pytolith
import Pytolith._TagSystem as ts
from Pytolith.Definitions import Definitions

from setuptools.command.build import build, SubCommand
from setuptools import setup, Command

import pathlib
import glob

import code_generator

class BuildDefinitionsPackage(Command, SubCommand):
     LAYOUTS_FILE = pathlib.Path("Pytolith")/"halo2.layouts"
     FAST_TAG_LOADERS = pathlib.Path("Pytolith")/"_TagBinary"/"_FastTagLoaders.py"
     def initialize_options(self) -> None:
          self.build_base = None
          self.build_lib = None

     def finalize_options(self):
          self.set_undefined_options('build',
                               ('build_base', 'build_base'),
                               ('build_lib', 'build_lib'))
     def _build_lib_path(self):
          return pathlib.Path(self.build_lib)
     def _get_output_file_path(self):
          return self._build_lib_path()/self.LAYOUTS_FILE
     def _get_fast_loaders_path(self):
          return self._build_lib_path()/self.FAST_TAG_LOADERS

     def run(self) -> None:
          print("BuildDefinitionsPackage", "run")
          defs = ts._load_default_definitions()
          defs_as_bytes = defs.dumps()
          output_file = self._get_output_file_path()
          with open(output_file, mode="wb") as compiled_file:
               compiled_file.write(defs_as_bytes)
          print("Done build tag definitions")
          # reload the definitions here to A) check if it works and B) get the version hash
          reloaded_definitions = Definitions.loads(defs_as_bytes)
          code_generator.generate_fast_loaders(reloaded_definitions, output_file_name=self._get_fast_loaders_path())

     def get_source_files(self) -> list[str]:
          source_files = glob.glob(f"Data/**/*.xml", recursive=True)
          return source_files

     def get_outputs(self) -> list[str]:
          packaged_defs = str(self._get_output_file_path())
          fast_loaders = str(self._get_fast_loaders_path())
          return [packaged_defs, fast_loaders]

     def get_output_mapping(self) -> dict[str, str]:
          sources = self.get_source_files()
          output_file = str(self._get_output_file_path)
          mapping = {source: output_file for source in sources}

          return mapping
          
class CustomBuild(build):
    sub_commands = build.sub_commands + [('build_definitions_package', None)]

setup(cmdclass={'build': CustomBuild, 'build_definitions_package': BuildDefinitionsPackage})