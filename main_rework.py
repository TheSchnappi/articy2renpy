import configparser
import logging
import json


logging.basicConfig(level=logging.DEBUG)


def filter_entries(model_list):
    """
    Takes the model list and filters the type of nodes we need for generating dialogues
    """
    filtered_list = []
    for node in model_list:
        if node['Type'] == "Dialogue":
            filtered_list.append(node)
        elif node['Type'] == "FlowFragment":
            filtered_list.append(node)
        elif node['Type'] == "DialogueFragment":
            filtered_list.append(node)
        elif node['Type'] == "Hub":
            filtered_list.append(node)
        elif node['Type'] == "Jump":
            filtered_list.append(node)
        elif node['Type'] == "Condition":
            filtered_list.append(node)
        elif node['Type'] == "Instruction":
            filtered_list.append(node)
    return filtered_list


def get_node_targets_id_by_node(node):
    """
    Takes a node and returns all IDs of the nodes it targets
    """
    target_list = []
    if node['Type'] == 'Dialogue' or node['Type'] == 'FlowFragment':
        # ToDo - Node End targets
        pass
    elif node['Type'] == 'Jump':
        target_list.append(node['Properties']['Target'])
    elif node['Type'] == "Condition":
        if_target   = node['Properties']['OutputPins'][0]['Connections'][0]['Target']
        else_target = node['Properties']['OutputPins'][1]['Connections'][0]['Target']
        target_list.append(if_target)
        target_list.append(else_target)
    else:
        if 'Connections' in node['Properties']['OutputPins'][0]:
            for target in node['Properties']['OutputPins'][0]['Connections']:
                target_list.append(target['Target'])
    return target_list


def get_label_ids(model_list):
    """
    Takes a model list and generates a list of IDs that will become RenPy labels
    
    Following conditions lead to the creation of a label:
    - Any target of an input pin by a Dialogue Node 
        - Start of the Dialogue container
    - Any target of Articy Jump nodes 
        - Since we will jump there
    - Hub Nodes
        - simple jump targets
    - Any target of an Condition Node 
        - If-code
    - Any node that has more then one target
        - merging of two or more node branches
    - Any node that is targeted by a node with more then one target
        - Choice menus
    """
    label_id_list = []
    for node in model_list:
        node_id = node['Properties']['Id']
        logging.debug('Checking Node {}....'.format(node_id))
        # If node is targeted by Dialogue InputPins
        if node['Type'] == 'Dialogue' or node['Type'] == 'FlowFragment':
            for connection in node['Properties']['InputPins'][0]['Connections']:
                label_id_list.append(connection['Target'])

        # If node is targeted by a Jump
        elif node['Type'] == 'Jump':
            logging.debug('....JUMP found, add its target Id')
            label_id_list.append(node['Properties']['Target'])

        # If node is a Hub
        elif node['Type'] == 'Hub':
            logging.debug('....HUB found, add its Id')
            label_id_list.append(node['Properties']['Id'])

        # If node is targeted by a Condition
        elif node['Type'] == 'Condition':
            logging.debug('....CONDITION found, add its targets Ids')
            node_targets = get_node_targets_id_by_node(node)
            label_id_list.extend(node_targets)

        # If node is targeted multiple times
        node_references = 0
        for node2 in model_list:
            target_ids = get_node_targets_id_by_node(node2)
            if node['Properties']['Id'] in target_ids:
                node_references += 1
        if node_references > 1:
            logging.debug('....Node referenced more than once ({}), add its Id'.format(node_references))
            label_id_list.append(node['Properties']['Id'])

        # If node is targeted by an node with with multiple output nodes
        node_targets = get_node_targets_id_by_node(node)
        if len(node_targets) > 1:
            logging.debug('....Node targets more than one node ({}), add its targets Ids'.format(node_references))
            label_id_list.extend(node_targets)
    label_id_list = list(set(label_id_list))
    return label_id_list


def get_node_by_id(node_id, model_list):
    """
    Returns the node from the model list by its node ID
    """
    for node in model_list:
        if node['Properties']['Id'] == node_id:
            return node


def get_parent_name_by_child_id(child_id, model_list):
    """
    Returns the parents name from the model list of the given child ID
    (Checks the given node by ID for its parent)
    """
    child_node = get_node_by_id(child_id, model_list)
    parent_name = get_parent_name_by_parent_id(child_node['Properties']['Parent'], model_list)
    return parent_name


def get_parent_name_by_parent_id(parent_id, model_list):
    """
    Returns the name of the given node ID from the model list
    """
    for node in model_list:
        if node['Properties']['Id'] == parent_id:
            return node['Properties']['DisplayName'].replace(" ", "_").lower()


def convert_dialogue_fragment(node, entity_nodes):
    """
    Converts a DialogueFragment node into RenPy code.
    """
    code_list = []
    dialogue_text = node['Properties']['Text'].replace('\r\n', '\\n')
    dialogue_stage_directions = node['Properties']['StageDirections']
    speaker_id = node['Properties']['Speaker']
    character = 'narrator'
    for node in entity_nodes:
        if node['Properties']['Id'] == speaker_id:
            if node['Properties']['ExternalId']:
                character = node['Properties']['ExternalId']
            else:
                character = node['Properties']['DisplayName'].replace(" ", "_").lower()

    if dialogue_stage_directions:
        code_list.append('    {}'.format(dialogue_stage_directions))
    # ToDo: speaker_id convert to true name
    if character == 'narrator':
        if dialogue_text:
            code_list.append('    \"{}\"'.format(dialogue_text))
    else:
        code_list.append('    {} \"{}\"'.format(character, dialogue_text))
    return code_list


def convert_hub(node):
    """
    Converts a Hub node into RenPy code.
    """
    code_list = []
    display_name = node['Properties']['DisplayName'].replace(" ", "_").lower()
    code_list.append('    # HUB {}'.format(display_name))
    return code_list


def convert_jump(node, model_list):
    """
    Converts a Jump node into RenPy code.
    """
    code_list = []
    code_list.append('    # JUMP node')
    target_id = node['Properties']['Target']
    parent_name = get_parent_name_by_child_id(target_id, model_list)
    code_list.append('    jump {}_{}'.format(parent_name, target_id))
    return code_list


def convert_condition(node, model_list):
    """
    Converts a Condition node into RenPy code.
    """
    code_list = []
    code_expression = node['Properties']['Expression']
    target_ids = get_node_targets_id_by_node(node)
    if_target_id = target_ids[0]
    if_parent_name = get_parent_name_by_child_id(if_target_id, model_list)
    else_target_id = target_ids[1]
    else_parent_name = get_parent_name_by_child_id(else_target_id, model_list)
    code_list.append('    if {}:'.format(code_expression))
    code_list.append('        jump {}_{}'.format(if_parent_name, if_target_id))
    code_list.append('    else:')
    code_list.append('        jump {}_{}'.format(else_parent_name, else_target_id))
    return code_list


def convert_instruction(node):
    """
    Converts an Instruction node into RenPy code.
    """
    code_list = []
    instruction_raw = node['Properties']['Expression']
    instruction_list = instruction_raw.split('\n')
    for instruction_line in instruction_list:
        code_list.append('    $ {}'.format(instruction_line))
    return code_list


def generate_renpy_code(node, model_list, label_ids, entity_nodes):
    renpy_code = []
    continue_code_generation = True
    if node['Type'] == 'DialogueFragment':
        node_code = convert_dialogue_fragment(node, entity_nodes)
        renpy_code.extend(node_code)
    elif node['Type'] == 'Hub':
        node_code = convert_hub(node)
        renpy_code.extend(node_code)
    elif node['Type'] == 'Jump':
        node_code = convert_jump(node, model_list)
        renpy_code.extend(node_code)
        continue_code_generation = False
    elif node['Type'] == 'Condition':
        node_code = convert_condition(node, model_list)
        renpy_code.extend(node_code)
        continue_code_generation = False
    elif node['Type'] == 'Instruction':
        node_code = convert_instruction(node)
        renpy_code.extend(node_code)

    if continue_code_generation:
        target_ids = get_node_targets_id_by_node(node)
        if len(target_ids) > 1:
            menu_code = generate_menu(target_ids, model_list)
            renpy_code.extend(menu_code)
        elif len(target_ids) == 1:
            target_id = target_ids[0]
            if target_id == node['Properties']['Parent']:
                logging.debug('....node targets its parent, end of dialogue reached')
                node_id = node['Properties']['Id']
                parent_name = get_parent_name_by_child_id(node_id, model_list)
                renpy_code.append('    jump {}_end'.format(parent_name))
            elif target_id not in label_ids:
                logging.debug('....node target is not a label, extend label with next node')
                target_node = get_node_by_id(target_id, model_list)
                recursive_code = generate_renpy_code(target_node, model_list, label_ids, entity_nodes)
                renpy_code.extend(recursive_code)
            else:
                logging.debug('....next node is label, make jump.')
                parent_name = get_parent_name_by_child_id(target_id, model_list)
                renpy_code.append('    jump {}_{}'.format(parent_name, target_id))

    return renpy_code


def generate_menu(target_ids, model_list):
    """
    Generates the code for a RenPy choice menu from the given target IDs.
    It sorts the menu based on the targeted nodes Y position in Articy.
    The target IDs have to be DialogueFragements for the "MenuText" entry or the conversion will fail.
    """
    menu_list = ['    menu:']
    unsorted_menu_nodes = []
    for node in model_list:
        node_id = node['Properties']['Id']
        if node_id in target_ids:
            if node['Type'] == 'DialogueFragment':
                unsorted_menu_nodes.append(node)
            else:
                raise ValueError("Menu Target '{}' is not a DialogueFragment!".format(node_id))
    # Sort Menu entries based on their Y position in Articy
    sorted_menu_nodes = sorted(unsorted_menu_nodes, key=lambda k: k['Properties']['Position']['y'])
    for node in sorted_menu_nodes:
        node_id = node['Properties']['Id']
        menu_condition = node['Properties']['InputPins'][0]['Text']
        parent_name = get_parent_name_by_parent_id(node['Properties']['Parent'], model_list)
        menu_text = node['Properties']['MenuText']
        if menu_condition:
            menu_list.append('        \"{}\" if {}:'.format(menu_text, menu_condition))
        else:
            menu_list.append('        \"{}\":'.format(menu_text))
        menu_list.append('            jump {}_{}'.format(parent_name, node_id))

    return menu_list


if __name__ == '__main__':
    logging.info("######################################")
    logging.info("STEP 1: Read Config")
    config = configparser.ConfigParser()
    config.read('config.ini')
    config_json_file = config['DEFAULT']['json_file']
    config_export_path = config['DEFAULT']['export_path']
    config_entities = config['DEFAULT']['entity_types'].split(";")

    logging.info("######################################")
    logging.info("STEP 2: Load JSON file")
    with open(config_json_file, encoding="utf-8") as file:
        articy_data = json.load(file)

    logging.info("######################################")
    logging.info("STEP 3: Gather data from JSON")

    logging.debug("Generating list of entities")
    entity_nodes = []
    for node in articy_data['Packages'][0]['Models']:
        if node['Type'] in config_entities:
            entity_nodes.append(node)

    logging.debug("Filter relevant node model data entries")
    filtered_model_list = filter_entries(articy_data['Packages'][0]['Models'])

    logging.debug("Generating list of nodes that become labels")
    label_ids = get_label_ids(filtered_model_list)

    logging.debug("Generating list of dialogue and FlowFragment nodes")
    dialogue_nodes =[]
    for node in filtered_model_list:
        if node['Type'] == 'Dialogue' or node['Type'] == 'FlowFragment':
            dialogue_nodes.append(node)

    logging.info("######################################")
    logging.info("STEP 3: Generate Dialogue Files")
    tmp_list = []
    for dialogue in dialogue_nodes:
        dialogue_output = []
        dialogue_id = dialogue['Properties']['Id']
        # Replace spaces with "_"
        dialogue_name = dialogue['Properties']['DisplayName'].replace(" ", "_").lower()

        logging.debug("Create Start label")
        dialogue_output.append('label {}_start:'.format(dialogue_name))
        dialogue_start_targets = []
        dialogue_start_connections = dialogue['Properties']['InputPins'][0]['Connections']
        for connection in dialogue_start_connections:
            dialogue_start_targets.append(connection['Target'])
        if len(dialogue_start_targets) == 1:
            jump_target = dialogue_start_targets[0]
            parent_name = get_parent_name_by_child_id(jump_target, filtered_model_list)
            dialogue_output.append('    jump {}_{}'.format(parent_name, jump_target))
        else:
            menu_list = generate_menu(dialogue_start_targets, filtered_model_list)
            dialogue_output.extend(menu_list)
        dialogue_output.append('')

        logging.debug("Create End label")
        dialogue_output.append('label {}_end:'.format(dialogue_name))
        dialogue_output.append('    # Please put this label into an other file and point it toward something you want to jump!')
        dialogue_output.append('    pass')
        dialogue_output.append('')

        logging.debug("Create the labels of the dialogue")
        for node in filtered_model_list:
            node_id = node['Properties']['Id']
            if node_id in label_ids and node['Properties']['Parent'] == dialogue_id:
                logging.debug("Child found")
                dialogue_output.append('label {}_{}:'.format(dialogue_name, node_id))
                renpy_code = generate_renpy_code(node, filtered_model_list, label_ids, entity_nodes)
                dialogue_output.extend(renpy_code)
                dialogue_output.append("")

        logging.debug("Export dialogue file")
        file_path = "{}{}.rpy".format(config_export_path, dialogue_name)
        with open(file_path, "w", encoding="utf-8") as dialogue_file:
            for line in dialogue_output:
                dialogue_file.write("{}\n".format(line))


    logging.info("######################################")

