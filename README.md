A simple python library for reading (and perhaps writing in the future) Halo 2 tag files. Allows for tags to be introspected on any platform without the hassle of using the official tools.

SemVer may eventually be used but for now the API is unstable and subject to change at any time. Tag layouts are [defined in XML](https://github.com/num0005/Halo2TagLayouts) in a separate repository and are compiled into a pickled format during package installation. The package license does not cover this layout metadata.

# Sample usage

```python
from Pytolith import TagSystem
import os

# initialize new tag system using layouts packaged with Pytolith
system = TagSystem()

MY_H2EK_TAGS_FOLDER = r"T:\SteamLibrary\steamapps\common\H2EK\tags"
BRUTE_TAG_PATH = r"objects\characters\brute\brute.biped"

path = os.path.join(MY_H2EK_TAGS_FOLDER, BRUTE_TAG_PATH)

# load the brute tag
tag1 = system.load_tag_from_path(path)
# inspect the feign_death_chance setting
print(tag1.fields.feign_death_chance)
```

If you want to edit the XML definitions first clone `https://github.com/num0005/Halo2TagLayouts` into a local path:

```shell
T:\> git clone https://github.com/num0005/Halo2TagLayouts
Cloning into 'Halo2TagLayouts'...
remote: Enumerating objects: 156, done.
remote: Counting objects: 100% (156/156), done.
remote: Compressing objects: 100% (96/96), done.
remote: Total 156 (delta 60), reused 156 (delta 60), pack-reused 0 (from 0)
Receiving objects: 100% (156/156), 384.26 KiB | 11.64 MiB/s, done.
Resolving deltas: 100% (60/60), done.
```

And then set the custom definitions when constructing the `TagSystem` object:

```python
from Pytolith.Definitions import Definitions
from Pytolith import TagSystem

custom_defintions = Definitions()
custom_defintions.load_from_xml(r"T:\Halo2TagLayouts")

system = TagSystem(tag_definitions=custom_defintions)
```

You will now be using the tag definitions from `T:\Halo2TagLayouts` instead of the ones packaged with the library.

# Using the package without install

Install the package using `pip` is the recommended way to use it, but if you are unable to to that or want to avoid installing it during development you can load the package directly. For instance `setup.py` does it like so:

```python
root_directory = pathlib.Path(os.path.abspath(__file__)).parent
sys.path.append(str(root_directory/"src"))
import Pytolith
```

This depends on the tag definitions being located in the `Data` folder. Make sure you initialize git submodules if you are doing this.


# Performance

Using PyPy is recommended as the tracing compiler provides a ~2x speed up on tag loading.

Installed packages include autogenerated tag readers which provide a minor (~10%) speed-up when using CPython. These can only be used if you use the tag definitions packaged with the library. See `code_generator.py` and `setup.py` for details on how the "fast loaders" are generated.

Installed packages also use `pickle`'d tag definitions, this provides a modest speed-up on first tag load.

