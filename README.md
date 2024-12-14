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

If you want to edit the XML definitions clone `https://github.com/num0005/Halo2TagLayouts` into a local path and then set the custom definitions when constructing the `TagSystem` object.


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
```python
	from Pytolith.Definitions import Definitions
	from Pytolith import TagSystem

	custom_defintions = Definitions()
	custom_defintions.load_from_xml(r"T:\Halo2TagLayouts")

	system = TagSystem(tag_definitions=custom_defintions)
```