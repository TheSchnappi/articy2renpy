# articy2renpy
A converter for artify:draft JSON to Ren'Py \*.rpy script files.

## How the Converter Works
The exporter takes your exported JSON articy:draft project and converts your Dialogues flow elements into Ren'Py commands and labels with one \*.rpy script file per Dialogue.
It also exports all of your in articy:draft defined variables in a separate \*.rpy script file with a label to call, to make the overall workflow in using articy:draft a little bit easier.

The supported flow elements inside a Dialogue node that are exported are:

- DialogueFragment
- Hub
- Jump
- Condition
- Instruction
- Dialogue

## Basic Setup:

1. You need a Python 3 environment for this script to run
2. The converter needs an articy:draft exported JSON file.
3. Copy/rename the config_example.ini to config.ini
3. Edit your config.ini configuration file to target your exported JSON file and the directory in which you want to save the converted rpy script files.
4. Run the script

## Configuration file options

- `json_file` - The path to your articy:draft JSON file that you want to convert.
- `export_path` - The path in which your converted rpy files should be placed.
- `file_name_prefix` - A prefix for exported files. If empty, no prefix will be added.
- `global_var_prefix` - The articy:draft variable set with the name of this key will be converted to global space in Ren'Py (GlobalVar.my_var -> my_var)
- `entity_features` - The list of Entities that the converter picks up for matching Entities and DialogueFragments. If you created your own entity features simply add them to the list, separated by `;`

## Supported Flow Elements

### Dialogue
For the converter, a dialogue node is a parent node that contains the complete dialogue tree of its children.
The dialogue node name is used for two parts:

- As the file name for the exported RenPy file
- As the prefix for its dialogue labels

Capital letters of the dialogue name are lowered and spaces are replaced by underscores during the export for label and file compatibility.
Each Dialogue gets a special start label created by the converter, called *[DialogueName]\_start* that represent the start pin of the Dialogue.
If a Dialogue end pin has no connection to any other flow element, it will create a *[DialogueName]\_end* label.

### DialogueFragment
A dialogue fragment is simply a spoken line of dialogue.

A DialogueFragment can be used in any one of the following combination:
- Stage direction + Full Text
- Only Stage direction
- Only Full Text

#### Entities:
The linked NPC that should speak this line. For more information see NPCs/Entities. Currently the converter will break if no Entity was linked, so make sure each DialogueFragment in your script has an Entity.

#### Menu Text:
The menu text is used when creating multiple choice menus and will be the displayed text choice of the menu for this branch.

#### Stage directions:
Stage directions can be used for simple one line renpy code and will be placed before the dialogue itself. There is no logic check here so make sure that stage directions are valid Ren'Py instructions.
For example you could use this to change the scene or show the characters emotions, change the scene, etc.

#### Full text:
This is simply text line that will be spoken.

### Hubs
Hubs are often used as jump points inside articy:draft, so they become labels that your dialogue tree can jump to.

#### Name:
The name will be converted to a label.

### Jump
Jumps are like RenPys jump statement and can be used to jump to a node inside the dialogue.

#### Target Node:
The Hub you want to jump to.

### Condition
A condition is a simple if-else check. It will be converted into an if-statement.

#### Expression:
Simply add your expression here.
The converter will try to convert simple articy:draft C# conditions into Python (`&&` -> `and`, `||` -> `or`, `!` -> `not`, `true` -> `True`, `false` -> `False`).

### Instruction
Instructions are code blocks and the converter simply adds a "$" sign before the expression. As a limitation of this, it only works for the first line of code.
Unfortunately articy:draft evaluates the expression of the instruction when exporting, so you often won't be able to place more then a simple variable definition...

#### Expression:
Add your one line of expression here.

## NPCs / Entities
In RenPy text is often spoken by a character that is in most cases defined as a unique character object.
These character objects are then referenced with a variable name that may or may not represents their ingame name.
For example this is a typical character definition from the RenPy documentation:
```
define e = Character("Eileen", who_color="#c8ffc8")
```

In articy:draft, NPCs are defined as a so called entity instead. For creating the dialogue, the converter takes the DialogueFragments linked entity and trys to use the entities "ExternalId" property for writing the line of dialogue when converting to RenPy. If the ExternalId is not set the exporter will use the DisplayName instead.
So if you have a DialogueFragment linked to the entity `Eileen`, make sure that the ExternalId is set to `e`.

Because articy:draft supports custom entity-templates that not always have to be NPCs, the exporter supports a custom keyword lists for identifying specific NPC entities. All you need to do is add your custom Type name (in the UI called "Technical Name") to the npc_types list in the config file, separated by a ";". The npc_types list is already populated with the default entries of articy:draft.

For creating text that is not spoken by anyone, simply create and use an NPC/Entity named "narrator" in articy:draft. The converter will then omit the name of spoken dialogue by the "narrator".

Please note: Entities are not exported or converted to RenPy, so make sure that your NPCs are also defined in your RenPy project!

## Known Limitations:
- Each new run will overwrite all existing files it generates, so modifying these files can be tricky. This unfortunately makes the *[DialogueName]\_end* jump hard to use. As a work around for now you can copy the exit jump into a new separate .rpy file and delete the original exit label. If you have a better solution, I am open for ideas.
- Because articy:draft uses C# style expressions and conditions to evaluate the dialogues in the presentation, while Ren'Py is written in Python, expressions and instructions are prone to fail. The converter tries to smooth the process with some simple string replacements for the most common. In the end you are likely better to just write your python code inside articy:draft and dismiss its presentation mode.


## FAQ:
**Q:** How do I create a choice menu? <br />
**A:** Connect the output of a node with multiple DialogueFragment nodes and use the Menu Text for defining the choices text.

**Q:** How can I add logic to a choice, for example show the option only if a value is lower then 3? <br />
**A:** With articy:draft you can place code at input and output pins. If the input pin of a choice has logic, it will be converted into an if-conditional for this choice.

**Q:** Do I have to use instruction nodes for changing variables or can I use the output pins too? <br />
**A:** You can also use the output pin of a node for setting instructions but with the same limitations.

**Q:** Is the Document feature supported? <br />
**A:** No, the Document feature is not supported by this converter. There are multiple problems with this feature and in the context of Ren'Py, writing linear dialogue with RenPy and a text editor is most likely a much better solution then the Document feature.
As a work around, you could copy&paste the nodes of the Document in your Dialogue node to make it somewhat work.

**Q:** Do I need to select or deselect something during the JSON export in articy:draft? <br />
**A:** You have to export at least Packages and GlobalVariables selected during the articy:draft JSON export.
