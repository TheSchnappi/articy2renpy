####################################
# articy:draft to Ren'Py Converter
####################################
#
# Copyright (c) 2020 TheSchnappi
#
# For the current version of this converter please look at:
# GitHub: https://github.com/TheSchnappi/articy2renpy
# Lemma Soft Forum: https://lemmasoft.renai.us/forums/viewtopic.php?f=51&t=59921
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import configparser
import datetime
import json
import re
import logging

DIALOGUE_NODE_TYPES = ["DialogueFragment", "Hub", "Jump", "Condition", "Instruction"]

# List that store all articy variables
global_variable_list = []
# List that stores all entities
entity_list = []
# List that stores all dialogues
dialogue_list = []
# List that stores all dialogue nodes
dialogue_node_list = []

logging.basicConfig(level=logging.DEBUG)


def translate_code_condition(code_condition):
    """
    Tries to convert the articy:draft Java/C# code conditions into Python and returns the converted string.

    true -> True
    false -> False
    || -> or
    && -> and
    ! -> not

    """
    # Remove the variable set from the string that was set in global_var_prefix
    converted_text = code_condition.replace("{}.".format(config_global_var_prefix), "")

    converted_text = converted_text.replace("true", "True")
    converted_text = converted_text.replace("false", "False")
    converted_text = converted_text.replace("&&", "and")
    converted_text = converted_text.replace("||", "or")
    # Regex replacement for "!" into "not", without killing "!="
    regex_match = True
    while regex_match:
        regex_match = re.search("![^=]", converted_text)
        if regex_match:
            regex_index = regex_match.start()
            converted_text = converted_text[:regex_index] + "not " + converted_text[regex_index + 1:]
    logging.debug("Converted Code: {} -> {}".format(code_condition, converted_text))
    return converted_text


def convert_entity(entity_data):
    """
    Reads and converts the data from an entity data set.
    Returns a dictionary with only the data set we need for the converter to work.
    (Id, ExternalId)
    """
    properties = entity_data["Properties"]
    if properties["ExternalId"]:
        entity_external_id = properties["ExternalId"]
    else:
        logging.warning("Entity has no ExternalId defined, fall back to DisplayName!")
        entity_external_id = properties["DisplayName"]
    entity_element = {"Id": properties["Id"],
                      "ExternalId": entity_external_id}

    logging.debug("Converted Entity: Id {} ({})".format(entity_element["Id"],
                                                        entity_element["ExternalId"]))
    return entity_element


def convert_node(node_data):
    """
    Reads and converts the data from an entity data set.
    If the node does not connect on its output to an other element, it will print an error.
    Returns a dictionary with only the data set we need for the converter to work.

    For all: Id, Parent, Type, Condition, Instruction, Target, Position
    For DialogueFragment: Speaker, Text, StageDirections, MenuText
    For Instruction: Expression
    For Condition: Expression
    For Hub: DisplayName
    """

    properties = node_data["Properties"]

    # Step 1: Read conditions and instructions on the input and output pins and converts them to python
    if properties["InputPins"][0]["Text"]:
        condition = translate_code_condition(properties["InputPins"][0]["Text"])
    else:
        condition = ""
    # Jumps need an exception for the output pin because they do not have any output pins
    if node_data["Type"] == "Jump":
        instruction = ""
    else:
        if properties["OutputPins"][0]["Text"]:
            instruction = translate_code_condition(properties["OutputPins"][0]["Text"])
        else:
            instruction = ""
    # returns all targeted node ids
    # Jumps need an exception because their target is not stored in an output pin but in a property element!
    target_list = []
    if node_data["Type"] == "Jump":
        target_list.append(properties["Target"])
    else:
        output_pins = properties["OutputPins"]
        for output_element in output_pins:
            if "Connections" not in output_element:
                print("- ERROR -")
                print("NODE HAS NO OUTGOING CONNECTIONS")
                print("Type:   {}".format(node_data["Type"]))
                print("ID:     {}".format(properties["Id"]))
                print("Parent: {}".format(properties["Parent"]))
            for connection in output_element["Connections"]:
                target_list.append(connection["Target"])

    # create the "default" data that all nodes share
    node_element = {"Id": properties["Id"],
                    "Parent": properties["Parent"],
                    "Type": node_data["Type"],
                    "Condition": condition,
                    "Instruction": instruction,
                    "Target": target_list,
                    # We need the Y position to sort choices in the menu later
                    "Position": properties["Position"]["y"]}

    # read and save the individual node fragments
    if node_data["Type"] == "DialogueFragment":
        node_element["Speaker"] = properties["Speaker"]
        node_element["Text"] = properties["Text"].replace("\r\n", "\\n")
        node_element["StageDirections"] = properties["StageDirections"]
        node_element["MenuText"] = properties["MenuText"]
    elif node_data["Type"] == "Instruction":
        node_element["Expression"] = properties["Expression"]
    elif node_data["Type"] == "Condition":
        node_element["Expression"] = properties["Expression"]
    elif node_data["Type"] == "Hub":
        node_element["DisplayName"] = properties["DisplayName"]

    logging.debug("Converted node data: Id {} ({})".format(node_element["Id"], node_element["Type"]))
    return node_element


def convert_dialogue(dialogue_data):
    """
    Reads and converts the data from an Dialogue data set.
    DisplayName will be already lowered here and empty spaces replaced by "_"
    Returns a dictionary with only the data set we need for the converter to work.

    (Id, DisplayName, "StartNode", "EndNode)
    """
    properties = dialogue_data["Properties"]
    display_name = properties["DisplayName"].lower().strip().replace(" ", "_")
    # Get the first connection of the input pin as our start node
    # Therefore a Dialogue should always have just one node at the start!
    start_node = properties["InputPins"][0]["Connections"][0]["Target"]

    # Check if the output pin of the node is connected to a label
    if "Connections" in properties["OutputPins"][0]:
        end_node = properties["OutputPins"][0]["Connections"][0]["Target"]
    else:
        end_node = None

    dialogue_element = {"Id": properties["Id"],
                        "DisplayName": display_name,
                        "Parent": properties["Parent"],
                        "StartNode": start_node,
                        "EndNode": end_node}
    return dialogue_element


def get_node_by_id(node_id, dialogue_node_list):
    """
    Takes a node id and returns the node from the dialogue_node_list
    """
    for dialogue_node in dialogue_node_list:
        if dialogue_node["Id"] == node_id:
            return dialogue_node
    return None


def get_label_name(node, dialogue_list):
    """
    Takes a node and returns the name for its label
    """
    for dialogue in dialogue_list:
        if dialogue["Id"] == node["Parent"]:
            label_name = "{}_{}".format(dialogue["DisplayName"], node["Id"])
            return label_name


########################################################################################################################
logging.info("Step 1: Read Configuration File")

config = configparser.ConfigParser()
config.read('config.ini')

config_json_file = config['DEFAULT']['json_file']
config_export_path = config['DEFAULT']['export_path']
config_file_name_prefix = config['DEFAULT']['file_name_prefix']
config_global_var_prefix = config['DEFAULT']['global_var_prefix']
config_entity_features = config['DEFAULT']['entity_features'].split(";")

########################################################################################################################
logging.info("Step 2: Read JSON File")

with open(config_json_file) as file:
    articy_data = json.load(file)

# Get only the Models data from the articy json data
package_model_list = articy_data["Packages"][0]["Models"]

########################################################################################################################
logging.info("Step 3: Store and Parse JSON Data")

for element in package_model_list:
    if element["Type"] in DIALOGUE_NODE_TYPES:
        dialogue_node_list.append(convert_node(element))
    elif element["Type"] in config_entity_features:
        entity_list.append(convert_entity(element))
    elif element["Type"] == "Dialogue":
        # store container Dialogue nodes
        dialogue_list.append(convert_dialogue(element))

logging.info("Stored {} nodes".format(len(dialogue_node_list)))
logging.info("Stored {} entities".format(len(entity_list)))
logging.info("Stored {} dialogues".format(len(dialogue_list)))

########################################################################################################################
logging.info("Step 4: Generate List of Ids that have to become labels")

# The condition for a node to have a label are:
#    1. More then one node targets this node
#    2. The node is a hub
#    3. The node is directly targeted by a "Jump" node
#    4. The node is directly targeted by a "Condition" node
#    5. The node is a choice (Input node has more than one target)?

label_id_list = []

node_id_cache = []
for node in dialogue_node_list:
    # Condition 1: Is the node targeted more then once?
    for target in node["Target"]:
        if target in node_id_cache:
            if target not in label_id_list:
                logging.debug("Node targeted more then once: {}".format(target))
                label_id_list.append(target)
        else:
            node_id_cache.append(target)
    # Condition 2: is the node a hub?
    if node["Type"] == "Hub":
        if node["Id"] not in label_id_list:
            logging.debug("Node is a Hub: {}".format(node["Id"]))
            label_id_list.append(node["Id"])
    # Condition 3: is a node targeted by a jump?
    if node["Type"] == "Jump":
        if node["Target"][0] not in label_id_list:
            logging.debug("Node is targeted by a Jump: {}".format(node["Target"][0]))
            label_id_list.append(node["Target"][0])
    # Condition 4: is a node targeted by a condition?
    if node["Type"] == "Condition":
        for target in node["Target"]:
            if target not in label_id_list:
                logging.debug("Node is targeted by a Condition: {}".format(target))
                label_id_list.append(target)
    # Condition 5: is a node targeting more then one node?
    if len(node["Target"]) > 1:
        for target in node["Target"]:
            if target not in label_id_list:
                logging.debug("Node is target of a Menu Choice: {}".format(target))
                label_id_list.append(target)

for dialogue in dialogue_list:
    # Add missing start nodes to the label list so we can jump to them.
    if dialogue["StartNode"] not in label_id_list:
        logging.debug("Add missing dialogue start node to label list ({})".format(dialogue["StartNode"]))
        label_id_list.append(dialogue["StartNode"])
    if dialogue["EndNode"]:
        if dialogue["EndNode"] not in label_id_list:
            logging.debug("Add missing node that is connected to a dialogue to label list ({})".format(dialogue["StartNode"]))
            label_id_list.append(dialogue["EndNode"])

########################################################################################################################
logging.info("Step 5: Generating Dialogue Trees")

for dialogue in dialogue_list:
    # Just some statistics for the header of the dialogue file
    statistics_node_count = 0
    statistics_dialogue_count = 0
    statistics_word_count = 0

    logging.info("==== Generating Dialogue {}".format(dialogue["DisplayName"]))
    logging.info("Create the start and end labels for Dialogue {}".format(dialogue["DisplayName"]))
    export_data = ["label {}_start:".format(dialogue["DisplayName"]),
                   "    jump {}_{}".format(dialogue["DisplayName"], dialogue["StartNode"]),
                   ""]

    if not dialogue["EndNode"]:
        export_data.append("")
        export_data.append("label {}_end:".format(dialogue["DisplayName"]))
        export_data.append("    pass")
        export_data.append("")

    # Comb the label id list for labels that have the dialogue as its parent
    logging.info("Start building labels")
    for label_id in label_id_list:
        node = get_node_by_id(label_id, dialogue_node_list)
        if not node:
            logging.info("Id of an Dialogue found - skipped")
        else:
            if node["Parent"] == dialogue["Id"]:
                logging.debug("Node of current dialogue found.")
                logging.info("== Create new label {}_{}:".format(dialogue["DisplayName"], node["Id"]))
                export_data.append("")
                export_data.append("label {}_{}:".format(dialogue["DisplayName"], node["Id"]))
                # Group linear nodes in one label together
                logging.info("Try to combine Nodes into one label")
                label_data = []
                combine_label = True
                while combine_label:
                    dialogue_choice_text = ""
                    if node["Type"] == "DialogueFragment":
                        logging.info("DialogueFragment detected")
                        statistics_dialogue_count += 1
                        statistics_word_count += len(node["Text"].split())
                        if node["StageDirections"] != "":
                            label_data.append("{}".format(node["StageDirections"]))
                        logging.debug("Get DialogueFragments speaker")
                        speaker_name = "narrator"
                        for entity in entity_list:
                            if entity["Id"] == node["Speaker"]:
                                if entity["ExternalId"] != "":
                                    speaker_name = entity["ExternalId"]
                                else:
                                    speaker_name = entity["DisplayName"]
                        if node["Text"] != "":
                            logging.info("Check if the DialogueFragment is located before a choice")
                            if len(node["Target"]) > 1:
                                logging.info("DialogueFragment located before a choice, add it in the menu")
                                if speaker_name.lower() != "narrator":
                                    dialogue_choice_text = "{} \"{}\"".format(speaker_name, node["Text"])
                                else:
                                    dialogue_choice_text = "\"{}\"".format(node["Text"])
                            else:
                                logging.debug("Write dialogue line for {}".format(speaker_name))
                                if speaker_name.lower() != "narrator":
                                    label_data.append("{} \"{}\"".format(speaker_name, node["Text"]))
                                else:
                                    label_data.append("\"{}\"".format(node["Text"]))
                    elif node["Type"] == "Hub":
                        logging.info("Hub detected")
                        label_data.append("# HUB: {}".format(node["DisplayName"]))
                    elif node["Type"] == "Jump":
                        logging.info("Jump detected")
                        label_data.append("# JUMP NODE:")
                        # Jump will be created further down when converter realizes that the next node is a label
                    elif node["Type"] == "Instruction":
                        logging.info("Instruction detected")
                        code = translate_code_condition(node["Expression"])
                        label_data.append("$ {}".format(code))
                    elif node["Type"] == "Condition":
                        logging.info("Condition detected")
                        code = translate_code_condition(node["Expression"])
                        label_data.append("if {}:".format(code))
                        jump_target_node = get_node_by_id(node["Target"][0], dialogue_node_list)
                        label_data.append("    jump {}".format(get_label_name(jump_target_node, dialogue_list)))
                        label_data.append("else:")
                        jump_target_node = get_node_by_id(node["Target"][1], dialogue_node_list)
                        label_data.append("    jump {}".format(get_label_name(jump_target_node, dialogue_list)))
                        combine_label = False
                    elif node["Instruction"] != "":
                        logging.info("Instruction detected")
                        code = translate_code_condition(node["Instruction"])
                        label_data.append("$ {}".format(code))

                    if combine_label:
                        # Check if a Choice Menu exists
                        if len(node["Target"]) > 1:
                            logging.info("RenPy Menu Choice detected with {} choices.".format(len(node["Target"])))
                            combine_label = False
                            label_data.append("menu:")
                            if dialogue_choice_text:
                                logging.debug("Add cached DialogueFragment text to the menu")
                                label_data.append("    {}".format(dialogue_choice_text))
                            # We first create a separate menu list so we can later sort them based on their Y position
                            menu_list = []
                            for target in node["Target"]:
                                menu_list.append(get_node_by_id(target, dialogue_node_list))
                            menu_list.sort(key=lambda x: x["Position"])
                            # Now create the choices based on the sorted list
                            for jump_target_node in menu_list:
                                # jump_target_node = get_node_by_id(target, dialogue_node_list)
                                statistics_word_count += len(jump_target_node["MenuText"].split())
                                if jump_target_node["Condition"] != "":
                                    logging.debug("Create Choice with if condition")
                                    code = translate_code_condition(jump_target_node["Condition"])
                                    label_data.append("    \"{}\" if {}:".format(jump_target_node["MenuText"], code))
                                else:
                                    logging.debug("Create Choice")
                                    label_data.append("    \"{}\":".format(jump_target_node["MenuText"]))
                                jump_label = get_label_name(jump_target_node, dialogue_list)
                                label_data.append("        jump {}".format(jump_label))

                        if node["Target"][0] in label_id_list:
                            logging.info("Detected that next Node will be a label, create jump")
                            combine_label = False

                            target_dialogue = None
                            for dial in dialogue_list:
                                if dial["Id"] == node["Target"][0]:
                                    logging.info("Target of the jump is a Dialogue!")
                                    target_dialogue = dial

                            if target_dialogue:
                                if node["Target"][0] == dialogue["Id"]:
                                    logging.debug("Getting the name of the dialogue")
                                    if dialogue["EndNode"]:
                                        # We check if the target is a Dialogue or a normal Node:
                                        end_is_dialogue = False
                                        for dial in dialogue_list:
                                            if dial["Id"] == dialogue["EndNode"]:
                                                label_data.append("jump {}_start".format(dial["DisplayName"]))
                                                end_is_dialogue = True
                                        if not end_is_dialogue:
                                            target_node = get_node_by_id(dialogue["EndNode"], dialogue_node_list)
                                            jump_node = get_label_name(target_node, dialogue_list)
                                            label_data.append("jump {}".format(jump_node))
                                    else:
                                        label_data.append("jump {}_end".format(dialogue["DisplayName"]))
                                else:
                                    label_data.append("jump {}_start".format(target_dialogue["DisplayName"]))
                            else:
                                jump_target_node = get_node_by_id(node["Target"][0], dialogue_node_list)
                                jump_label = get_label_name(jump_target_node, dialogue_list)
                                label_data.append("jump {}".format(jump_label))
                        elif node["Target"][0] == dialogue["Id"]:
                            logging.info("Node targets parent Dialogue, jump to End block")
                            combine_label = False
                            label_data.append("jump {}_end".format(dialogue["DisplayName"]))
                        else:
                            logging.debug("Get next node")
                            node = get_node_by_id(node["Target"][0], dialogue_node_list)

                logging.info("Combining label finished")
                # Append the generated lines to the export data list
                for label_line in label_data:
                    export_data.append("    {}".format(label_line))

    logging.info("Create dialogue file for {}".format(dialogue["DisplayName"]))
    export_header = []
    export_header.append("###############################################################################")
    export_header.append("# Dialogue {}".format(dialogue["DisplayName"]))
    export_header.append("# Exported from articy:draft 3")
    export_header.append("# Exported {}".format(datetime.datetime.today().strftime('%Y-%m-%d - %H:%M:%S')))
    export_header.append("# {} nodes with {} lines of dialogue and {} words of text".format(statistics_node_count,
                                                                                            statistics_dialogue_count,
                                                                                            statistics_word_count))
    export_header.append("###############################################################################")
    if config_file_name_prefix:
        file_name = "{}_{}.rpy".format(config_file_name_prefix, dialogue["DisplayName"])
    else:
        file_name = "{}.rpy".format(dialogue["DisplayName"])
    with open("{}{}".format(config_export_path, file_name), "w") as dialogue_file:
        for line in export_header:
            dialogue_file.write("{}\n".format(line))
        for line in export_data:
            dialogue_file.write("{}\n".format(line))

    logging.info("Create global variable definition file")
    export_header = []
    export_header.append("###############################################################################")
    export_header.append("# Global Game Variables")
    export_header.append("# Exported from articy:draft 3")
    export_header.append("# Exported {}".format(datetime.datetime.today().strftime('%Y-%m-%d - %H:%M:%S')))
    export_header.append("###############################################################################")
    file_name = "game_variables.rpy".format()
    with open("{}/{}".format(config_export_path, file_name), "w") as variables_file:
        for line in export_header:
            variables_file.write("{}\n".format(line))
        variables_file.write("label init_articy_vars:\n")
        for line in global_variable_list:
            variables_file.write("   $ {}\n".format(line))
        variables_file.write("   return\n")
