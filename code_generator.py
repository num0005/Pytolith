## Copyright 2024 <num0005@outlook.com>, some rights reserved
##
## This file is part of the Pytolith project licensed under the terms of the MIT license, see COPYING for more details
## This notice must be retained in all copies of this file

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
sys.path = [str(root_directory/"src")] + sys.path

import Pytolith
import Pytolith.Definitions as definitions
from Pytolith.Definitions.Layout import _UNPACKAGE_TAG_RAW_SIZES, FIELD_TYPE, FieldSetDef, LayoutDef
from Pytolith._TagLoader.Loader import _TagLoadingState
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
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var: str) -> str:
          """Code for reading the field"""
          ...
     def is_applicable(self, field_def: FIELD_TYPE, loader_function_name: str):
          """Does it apply to this field?"""
          ...
     def is_single_line_reader(self, field_def: FIELD_TYPE):
          """
         	Does the reader use more than one line? 
          Single line readers simply return the read statement, while multiline readers write to the code stream
          """
          return True
     def length_for_tag_reference(self, field_def):
          """
          When reading the tag to build a tag reference library, what is the length of this field?
          Return None if the field needs to be read even in that mode.
          """
          return None
     
class PyStructTupleReader(SpecialCasedReader):
     def __init__(self, struct_name: str, length: int, simple_reader_name: str):
          self.struct_name = struct_name
          self.length = length
          self.simple_reader_name = simple_reader_name
     def generate_cached_locals(self, stream: CodeWriter, state_var: str):
          stream.cache_object_attribute(self.struct_name, state_var)
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var: str):
          return f"{self.struct_name}.unpack({stream_var}.read({self.length}))"
     def is_applicable(self, field_def: FIELD_TYPE, loader_function_name: str):
          return self.simple_reader_name == loader_function_name
     def length_for_tag_reference(self, field_def):
          return self.length
     
class PyStructSingleReader(PyStructTupleReader):
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var: str):
          return super().generate_read_code(stream, field_def, stream_var) + "[0]"
     
class PyPadReader(SpecialCasedReader):
	def __init__(self):
		super().__init__()
	def generate_cached_locals(self, stream, state_var):
		return super().generate_cached_locals(stream, state_var)
	def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var):
		if field_def.tag == 'pd64':
			return 'None'
		DATA_VAR = "pad_data"
		stream.writeline("try:")
		case1 = stream.indent()
		case1.writeline(f"{DATA_VAR} = bytes({stream_var}.read({field_def.length}))")
		stream.writeline("except:")
		case2 = stream.indent()
		case2.writeline(f"{DATA_VAR} = bytes({stream_var}.read({stream_var}.length_left()))")
  
		return DATA_VAR
  
	def is_applicable(self, field_def, loader_function_name):
		return field_def.type in ["Pad", "Skip"]
	def is_single_line_reader(self, field_def):
		return field_def.tag == 'pd64'
	def length_for_tag_reference(self, field_def):
		if field_def.tag == 'pd64':
			return 0
		return field_def.length

class SpecialCasedReaderByFieldType(SpecialCasedReader):
     def __init__(self, field_type: str):
          self.field_type = field_type
     def is_applicable(self, field_def, loader_function_name):
          return self.field_type == field_def.type

class PyReaderBytesSize(SpecialCasedReaderByFieldType):
     def __init__(self, field_type: str, size: int):
          super().__init__(field_type)
          self.size = size
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var):
          return f"bytes({stream_var}.read({self.size}))"
     def length_for_tag_reference(self, field_def):
          return self.size
     
class PyReaderStringSize(SpecialCasedReaderByFieldType):
     def __init__(self, field_type: str, size: int):
          super().__init__(field_type)
          self.size = size
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var):
          return f"{stream_var}.read_string({self.size})"
     def length_for_tag_reference(self, field_def):
          return self.size
     
class PyReaderNoData(SpecialCasedReaderByFieldType):
     def generate_read_code(self, stream: CodeWriter, field_def: FIELD_TYPE, stream_var):
          return f"None"
     def length_for_tag_reference(self, field_def):
          return 0
     
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
     ### pad readers
     PyPadReader(),
     ### bytes-only readers
     PyReaderBytesSize("VertexBuffer", 0x20),
     PyReaderBytesSize("Ptr", 4),
     ## str-only readers
     PyReaderStringSize("String", 0x20),
     PyReaderStringSize("LongString", 0x100),
     ### "readers" for fields that don't actually contain any data
     PyReaderNoData("Explanation"),
     PyReaderNoData("Custom"),
]
          
def build_code_for_layout_version(defintion: FieldSetDef,  stream: CodeWriter, tag_ref_reader: bool, state_var: str, es_stream_var: str, fields_var: str, data_var: str):
     field_loaders_used_standard = set()
     field_loaders_used_special = set()
     fast_loaders_used: set[SpecialCasedReader] = set()

     # create a fake loading state object
     # used to detect semi-automatically what loaders can be special-cased
     # as well as which ones need the field def
     fake_loading_state = _TagLoadingState({}, None, None, False)
     fake_loading_state._setup_tag_readers()
 
     @dataclass 
     class LoadStatement:
          @property
          def field_type(self):
               return self.field_def.type
          
          field_def: FIELD_TYPE
          """Field definition"""
          field_index: int
          """Field index in the definitions"""
          use_field_index: bool
          """Does the reader use the field definition? Should probably be False for any `special_reader` functions"""
          special_reader: None|SpecialCasedReader
          """Special case reader, if set the data will be read directly instead of calling out to a reader function"""
          skip_ahead: None|int
          """How far to skip ahead, only valid for tag reference only readers. 0 != None, as None flags fields that need to be read while 0 indicates the field can be skipped but is zero length"""

     load_statements: list[LoadStatement] = []
  
     for i in range(len(defintion.merged_fields)):
          field_def = defintion.merged_fields[i]
          use_field_index = field_def.type in fake_loading_state._tag_readers_special_field.keys()
          loader_function = fake_loading_state._tag_readers_special_field[field_def.type] if use_field_index else fake_loading_state._tag_readers[field_def.type]

          custom_fast_reader = next((reader for reader in SPECIAL_CASE_READERS if reader.is_applicable(field_def, loader_function.__name__)), None)
          
          skip_ahead = None
          if custom_fast_reader:
               skip_ahead = custom_fast_reader.length_for_tag_reference(field_def)
          else:
               skip_ahead = _UNPACKAGE_TAG_RAW_SIZES.get(field_def.type, None)

          load_statements.append(LoadStatement(field_def, i, use_field_index, custom_fast_reader, skip_ahead))
          
          # skip marking readers as used if they would have been skipped
          if tag_ref_reader and skip_ahead is not None:
               continue
  
          if custom_fast_reader:
               fast_loaders_used.add(custom_fast_reader)
          elif use_field_index:
               field_loaders_used_special.add(field_def.type)
          else:
               field_loaders_used_standard.add(field_def.type)
     
     if tag_ref_reader:
          optimized_load_statements: list[LoadStatement] = []
          previous_skip_field = None
          for statement in load_statements:
               # is this an unskippable read?
               if statement.skip_ahead is None:
                    previous_skip_field = None
                    optimized_load_statements.append(statement)
                    continue
               # mergable statement otherwise
               if previous_skip_field is None:
                    # make and insert a "fake" statement to indicate skippable data
                    previous_skip_field = LoadStatement(None, -1, False, PyReaderNoData("Fake Field"), 0)
                    optimized_load_statements.append(previous_skip_field)
               previous_skip_field.skip_ahead += statement.skip_ahead
          
          # remove last entry if it's just a skip
          # this simplifies our error handling logic
          # while also removing a useless statement
          if len(optimized_load_statements) > 0 and optimized_load_statements[-1].skip_ahead is not None:
               optimized_load_statements = optimized_load_statements[:-1]
          # check if this would result in no-op function
          if len(optimized_load_statements) == 0:
               return None
          load_statements = optimized_load_statements
               
     def local_reader_name(field_name):
          return f"{field_name}_reader"
     # cache reader lookup dicts
     if field_loaders_used_standard:
          stream.writeline(f"READERS = {state_var}._tag_readers")
     if field_loaders_used_special:
          stream.writeline(f"SPECIAL_READERS = {state_var}._tag_readers_special_field")
     stream.writeline()
     if not tag_ref_reader:
          stream.writeline(f"append = {data_var}.append")
     cached_tag_refs = False
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
          if tag_ref_reader and load_statement.skip_ahead is not None:
               if load_statement.skip_ahead != 0:
                    stream.writeline(f"{es_stream_var}.skip({load_statement.skip_ahead})")
               continue
          
          if load_statement.special_reader:
               value_state = load_statement.special_reader.generate_read_code(stream, load_statement.field_def, es_stream_var)
          elif load_statement.use_field_index:
               # cache the tag def unless we are only reading the tag refs
               if not tag_ref_reader:
                    stream.writeline(f"fd = {field_def_state}")
                    field_def_state = "fd"
               value_state = f"{local_reader_name(load_statement.field_type)}({es_stream_var}, {field_def_state})"
          else:
               value_state = f"{local_reader_name(load_statement.field_type)}({es_stream_var})"
          if not tag_ref_reader:
               field_state = f"_TagField({field_def_state}, {value_state})"
               stream.writeline(f"append({field_state})")
          elif load_statement.field_def.type == "TagReference":
               # write the value only if it's a tag reference
               if not cached_tag_refs:
                    stream.writeline(f"append = {state_var}._tag_references.append")
               stream.writeline(f"append({value_state})")
          else:
               # otherwise just read the data and discard it
               stream.writeline(f"{value_state}")
     stream.writeline()
     return True
  
def build_loader_for_layout_version(defintion: LayoutDef, only_read_tag_ref: bool, version: int, stream: CodeWriter):
     function_name = "__reader_" + defintion.unique_id.replace(":", "__") + f"_version_{version}"
     if only_read_tag_ref:
          function_name = "__tag_refs" + function_name
     STATE_VAR = "arg_loader"
     STREAM_VAR = "arg_element"
     FIELDS_VAR = "arg_defs"
     DATA_OUT_FIELD = "data_out"
     ARGS = (STATE_VAR, STREAM_VAR, FIELDS_VAR, DATA_OUT_FIELD)
     function_code_stream = stream.write_function(function_name, ARGS)
     function_code_stream.write_docstring("Autogenerated internal function, DO NOT CALL DIRECTLY.")
     should_use = build_code_for_layout_version(defintion.versions[version], function_code_stream, only_read_tag_ref, *ARGS)

     return function_name, should_use

def build_loader_for_layout(defintion: LayoutDef, only_read_tag_ref: bool, file: CodeWriter):
     stream = CodeWriter()
     stream.indent_level = file.indent_level
     loader_functions_for_version = []
     should_use = only_read_tag_ref
     for version in range(len(defintion.versions)):
          function_stream = CodeWriter()
          function_stream.write_commment(f"Static loader for {defintion.unique_id} for version {version}")
          function_stream.write_commment(f"This function is automatically generated, do not call it directly or edit it")
          function_name, passed = build_loader_for_layout_version(defintion, only_read_tag_ref, version, function_stream)
          if passed or not only_read_tag_ref:
               stream.writeline()
               stream.stream.write(str(function_stream))
               stream.writeline()
          else:
               function_name = None
          loader_functions_for_version.append(function_name)
          if passed or only_read_tag_ref:
               should_use = True
     
     if should_use:
          file.stream.write(str(stream))
          return tuple(loader_functions_for_version)
     else:
          return None
     
def write_layout_table(stream: CodeWriter, name: str, loader_functions):
     stream.writeline(name + " = {")
     entry_stream = stream.indent()
     for key, functions in loader_functions.items():
          funcs_as_strings = (f or "None" for f in functions)
          function_string = ",".join(funcs_as_strings)
          if len(functions) == 1:
               function_string += ','
          entry_stream.writeline(f"'{key}' : ({function_string}),")
     stream.writeline("}")

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
     loader_functions_tag_ref: dict[str, tuple[str]] = dict()
     for id, layout in defs.id_to_layout.items():
          loaders_per_version = build_loader_for_layout(layout, False, stream)
          if loaders_per_version:
               loader_functions[id] = loaders_per_version
          loader_functions_tag_ref[id] = build_loader_for_layout(layout, True, stream)

     write_layout_table(stream, "LAYOUT_READERS", loader_functions)
     stream.writeline()
     write_layout_table(stream, "LAYOUT_READERS_TAG_REF", loader_functions_tag_ref)
     stream.writeline(f"LAYOUT_VERSION = {repr(version_info)}")
     
def generate_fast_loaders(defs: definitions.Definitions, output_file_name: str = "src/Pytolith/_TagLoader/_FastTagLoaders.py"):
     print(f"Writing fast loaders to {output_file_name}")
     with open(output_file_name, "w") as f:
          code = CodeWriter()
          build_accelerated_loads(defs, defs.version_hash, code)
          f.write(code.stream.getvalue())
          
     
     
if __name__ == "__main__":
     system = Pytolith.TagSystem("")
     generate_fast_loaders(system.tag_definitions)