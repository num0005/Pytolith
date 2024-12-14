from dataclasses import dataclass, field
import datetime
import os
import pathlib
import sys
from typing import Protocol
import gc

# load unpackage module
root_directory = pathlib.Path(os.path.abspath(__file__)).parent
sys.path.append(str(root_directory/"src"))

import Pytolith
import Pytolith.Definitions as definitions
from Pytolith.Definitions.Layout import FIELD_TYPE, FieldSetDef, LayoutDef
from Pytolith.TagLoader.Loader import _TagLoadingState
import io
from Pytolith.TagTypes import TagField as _TagField

@dataclass
class CodeWriter():
     stream: io.StringIO = field(default_factory=io.StringIO)
     indent_level: int = 0
     
     def write_docstring(self, docstring):
          """
          Write a docstring at the current indent level
          """
          self.stream.write(" "*4*self.indent_level)
          self.stream.write('"""')
          self.stream.write("\n")
          self.stream.write(docstring)
          self.stream.write("\n")
          self.stream.write('"""')
          self.stream.write("\n")
     
     def writeline(self, line = ""):
          self.stream.write(" "*4*self.indent_level)
          self.stream.write(line)
          self.stream.write("\n")
          
     def cache_object_attribute(self, local, object):
          self.writeline(f"{local} = {object}.{local}")

     def indent(self, indent = 1):
          return CodeWriter(self.stream, self.indent_level + indent)
     
     def write_function(self, name: str, arguments: tuple[str]):
          arguments = tuple(arguments)
          if len(arguments) == 1:
               self.writeline(f"def {name}({arguments[0]}):")
          else:
               arguments_string = ",".join(arguments)
               self.writeline(f"def {name}({arguments_string}):")
          return self.indent(1)
     
     def write_commment(self, comment):
          self.writeline("#\t" + comment)
          
     def __str__(self):
          return self.stream.getvalue()
          
class SpecialCasedReader(Protocol):
     def generate_cached_locals(self, stream: CodeWriter, state_var: str):
          """Emit code to cache any local variables needed if this reader is used"""
          ...
     def generate_read_code(self, stream_var: str) -> str:
          """Code for reading the field"""
          ...
     def is_applicable(self, field_def: FIELD_TYPE, loader_function_name: str):
          """Does it apply to this field?"""
          ...
     
class PyStructTupleReader(SpecialCasedReader):
     def __init__(self, struct_name: str, length: int, simple_reader_name: str):
          self.struct_name = struct_name
          self.length = length
          self.simple_reader_name = simple_reader_name
     def generate_cached_locals(self, stream: CodeWriter, state_var: str):
          stream.cache_object_attribute(self.struct_name, state_var)
     def generate_read_code(self, stream_var: str):
          return f"{self.struct_name}.unpack({stream_var}.read({self.length}))"
     def is_applicable(self, field_def: FIELD_TYPE, loader_function_name: str):
          return self.simple_reader_name == loader_function_name
     
class PyStructSingleReader(PyStructTupleReader):
     def generate_read_code(self, stream_var: str):
          return super().generate_read_code(stream_var) + "[0]"
     
SPECIAL_CASE_READERS: list[SpecialCasedReader] = [
     ### primitive struct single value readers ###
     PyStructSingleReader("s_real", 4, "read_real"),
     PyStructSingleReader("s_char", 1, "read_char_integer"),
     PyStructSingleReader("s_short", 2, "read_short_integer"),
     PyStructSingleReader("s_long", 4, "read_long_integer"),
     PyStructSingleReader("s_uchar", 1, "read_uchar_integer"),
     PyStructSingleReader("s_ushort", 2, "read_ushort_integer"),
     PyStructSingleReader("s_ulong", 4, "read_ulong_integer"),
     ### primitive struct multi value readers ###
     PyStructTupleReader("s_2short", 4, "read_two_shorts"),
     PyStructTupleReader("s_2real", 8, "read_two_reals"),
     PyStructTupleReader("s_3real", 12, "read_three_reals"),
     PyStructTupleReader("s_4real", 16, "read_four_reals"),
]
          
def build_code_for_layout_version(defintion: FieldSetDef, stream: CodeWriter, state_var: str, es_stream_var: str, fields_var: str, data_var: str):
     field_loaders_used_standard = set()
     field_loaders_used_special = set()
     fast_loaders_used: set[SpecialCasedReader] = set()

     # create a fake loading state object
     # used to detect semi-automatically what loaders can be special-cased
     # as well as which ones need the field def
     fake_loading_state = _TagLoadingState({}, None, False)
     fake_loading_state._setup_tag_readers()
 
     @dataclass 
     class LoadStatement:
          field_type: str
          field_index: int
          use_field_index: bool
          special_reader: None|SpecialCasedReader

     load_statements: list[LoadStatement] = []
  
     for i in range(len(defintion.merged_fields)):
          field_def = defintion.merged_fields[i]
          use_field_index = field_def.type in fake_loading_state._tag_readers_special_field.keys()
          loader_function = fake_loading_state._tag_readers_special_field[field_def.type] if use_field_index else fake_loading_state._tag_readers[field_def.type]

          custom_fast_reader = next((reader for reader in SPECIAL_CASE_READERS if reader.is_applicable(field_def, loader_function.__name__)), None)

          load_statements.append(LoadStatement(field_def.type, i, use_field_index, custom_fast_reader))
  
          if custom_fast_reader:
               fast_loaders_used.add(custom_fast_reader)
          elif use_field_index:
               field_loaders_used_special.add(field_def.type)
          else:
               field_loaders_used_standard.add(field_def.type)
     def local_reader_name(field_name):
          return f"{field_name}_reader"
     # cache reader lookup dicts
     if field_loaders_used_standard:
          stream.writeline(f"READERS = {state_var}._tag_readers")
     if field_loaders_used_special:
          stream.writeline(f"SPECIAL_READERS = {state_var}._tag_readers_special_field")
     stream.writeline()
     stream.writeline(f"append = {data_var}.append")
     stream.writeline()
     # cache the actual readers
     for reader in field_loaders_used_standard:
          reader_name = local_reader_name(reader)
          stream.writeline(f"{reader_name} = READERS['{reader}']")
     for reader in field_loaders_used_special:
          reader_name = local_reader_name(reader)
          stream.writeline(f"{reader_name} = SPECIAL_READERS['{reader}']")
     for fast_reader in fast_loaders_used:
          fast_reader.generate_cached_locals(stream, state_var)
     # generate load commands
     for load_statement in load_statements:
          field_def_state = f"{fields_var}[{load_statement.field_index}]"
          if load_statement.special_reader:
               value_state = load_statement.special_reader.generate_read_code(es_stream_var)
          elif load_statement.use_field_index:
               stream.writeline(f"fd = {field_def_state}")
               field_def_state = "fd"
               value_state = f"{local_reader_name(load_statement.field_type)}({es_stream_var}, {field_def_state})"
          else:
               value_state = f"{local_reader_name(load_statement.field_type)}({es_stream_var})"
          field_state = f"_TagField({field_def_state}, {value_state})"
          stream.writeline(f"append({field_state})")
     stream.writeline()
     return True
  
def build_loader_for_layout_version(defintion: LayoutDef, version: int, stream: CodeWriter):
     function_name = "__reader_" + defintion.unique_id.replace(":", "__") + f"_version_{version}"
     STATE_VAR = "arg_loader"
     STREAM_VAR = "arg_element"
     FIELDS_VAR = "arg_defs"
     ARGS = (STATE_VAR, STREAM_VAR, FIELDS_VAR, "data_out")
     function_code_stream = stream.write_function(function_name, ARGS)
     function_code_stream.write_docstring("Autogenerated internal function, DO NOT CALL DIRECTLY.")
     should_use = build_code_for_layout_version(defintion.versions[version], function_code_stream, *ARGS)

     return function_name, should_use

def build_loader_for_layout(defintion: LayoutDef, file: CodeWriter):
     stream = CodeWriter()
     stream.indent_level = file.indent_level
     loader_functions_for_version = []
     should_use = False
     for version in range(len(defintion.versions)):
          stream.write_commment(f"Static loader for {defintion.unique_id} for version {version}")
          stream.write_commment(f"This function is automatically generated, do not call it directly or edit it")
          function_name, passed = build_loader_for_layout_version(defintion, version, stream)
          stream.writeline()
          stream.writeline()
          loader_functions_for_version.append(function_name)
          if passed:
               should_use = True
     
     if should_use:
          file.stream.write(str(stream))
          return tuple(loader_functions_for_version)
     else:
          return None

def build_accelerated_loads(defs: definitions.Definitions, version_info: str, stream: CodeWriter):
     """Generate a python file containing fast tag loaders"""
     
     stream.write_docstring(f"Automatically generated layout readers, DO NOT USE ANY FUNCTIONS FROM THIS FILE or import this module outside of Pytolith itself.")
     stream.write_commment(f"This file has been automatically generated at {datetime.datetime.now()}")
     stream.write_commment(f"Generator script: {__file__}")
     stream.write_commment(f"Binary definitions version: {defs.version_hash}")
     stream.write_commment(f"XML definitions loaded from: {defs._xml_load_path}")
     stream.write_commment(f"Edit the XML defintions and rebuild the wheel to modify the contents of this file.")
     stream.writeline()
     stream.writeline("from Pytolith.TagTypes import TagField as _TagField")
     loader_functions: dict[str, tuple[str]] = dict()
     for id, layout in defs.id_to_layout.items():
          loaders_per_version = build_loader_for_layout(layout, stream)
          if loaders_per_version:
               loader_functions[id] = loaders_per_version
     stream.writeline("LAYOUT_READERS = {")
     entry_stream = stream.indent()
     for key, functions in loader_functions.items():
          function_string = ",".join(functions)
          if len(functions) == 1:
               function_string += ','
          entry_stream.writeline(f"'{key}' : ({function_string}),")
          
     stream.writeline("}")
     stream.writeline(f"LAYOUT_VERSION = {repr(version_info)}")
     
def generate_fast_loaders(defs: definitions.Definitions, output_file_name: str = "src/Pytolith/TagLoader/_FastTagLoaders.py"):
     print(f"Writing fast loaders to {output_file_name}")
     with open(output_file_name, "w") as f:
          code = CodeWriter()
          build_accelerated_loads(defs, defs.version_hash, code)
          f.write(code.stream.getvalue())
          
     
     
if __name__ == "__main__":
     system = Pytolith.TagSystem()
     generate_fast_loaders(system.tag_definitions)