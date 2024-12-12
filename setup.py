# load unpacked library
import pathlib
import os
import sys

# load unpackage module
root_directory = pathlib.Path(os.path.abspath(__file__)).parent
sys.path.append(str(root_directory/"src"))
import Pytolith
import Pytolith._TagSystem as ts

from setuptools.command.build import build, SubCommand
from setuptools import setup, Command

import pathlib
import glob

class BuildDefinitionsPackage(Command, SubCommand):
	LAYOUTS_FILE = pathlib.Path("Pytolith")/"halo2.layouts"
	def initialize_options(self) -> None:
		self.build_base = None
		self.build_lib = None

	def finalize_options(self):
		self.set_undefined_options('build',
                               ('build_base', 'build_base'),
                               ('build_lib', 'build_lib'))

	def _get_output_file_path(self):
		return pathlib.Path(self.build_lib)/self.LAYOUTS_FILE
	def run(self) -> None:
		print("BuildDefinitionsPackage", "run")
		defs = ts._load_default_definitions()
		defs_as_bytes = defs.dumps()
		output_file = self._get_output_file_path()
		with open(output_file, mode="wb") as compiled_file:
			compiled_file.write(defs_as_bytes)
	def get_source_files(self) -> list[str]:
		source_files = glob.glob(f"Data/**/*.xml", recursive=True)
		return source_files
	def get_outputs(self) -> list[str]:
		return [str(self._get_output_file_path())]
	def get_output_mapping(self) -> dict[str, str]:
		sources = self.get_source_files()
		output_file = str(self._get_output_file_path)
		mapping = {source: output_file for source in sources}

		return mapping
          
class CustomBuild(build):
    sub_commands = build.sub_commands + [('build_definitions_package', None)]

setup(cmdclass={'build': CustomBuild, 'build_definitions_package': BuildDefinitionsPackage})