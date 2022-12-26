import time
import os
import struct
import subprocess
import json

BUTTONS = {
    398: "red",
    399: "green",
    400: "yellow",
    401: "blue",
    402: "ch_up",
    403: "ch_down",
    207: "play",
    119: "pause",
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    1038: "prime",
    1037: "netflix"
}


def main():
    """MAIN"""

    button_map = get_button_map()
    input_loop(input_device="/dev/input/event3", button_map=button_map)


def input_loop(input_device, button_map):
    infile_path = input_device
    input_format = "llHHI"
    event_size = struct.calcsize(input_format)
    in_file = open(infile_path, "rb")
    event = in_file.read(event_size)

    code_wait = None  # Are we waiting for button up
    code_wait_start = None
    while event:
        (tv_sec, tv_usec, type, code, value) = struct.unpack(input_format, event)
        if code in BUTTONS:

            print("button code: %s" % code)
            print("button value: %s" % value)
            print("code_wait: %s" % code_wait)
            print("code_wait_start: %s" % code_wait_start)

            if not code_wait and value == 1:  # Start waiting for button up
                print("%s button down" % BUTTONS[code])
                code_wait = code
                code_wait_start = time.time()
            elif code_wait == code and value == 0:

                # We need to ignore long presses
                now = time.time()
                button_hold_duration = now - code_wait_start
                print("button_hold_duration: %s" % button_hold_duration)

                code_wait = None
                code_wait_start = None

                if button_hold_duration < 1.0:
                    print("%s button up" % BUTTONS[code])
                    fire_event(code, button_map)
                else:
                    print("Ignoring long press of %s" % BUTTONS[code])
        elif code:
            print('Unknown button pressed. (code=%s)' % code)
        event = in_file.read(event_size)

    in_file.close()


def get_button_map():
    """ Read the json config file """
    config_path = os.path.join(os.path.dirname(__file__), 'magic_mapper_config.json')
    with open(config_path) as config_file:
        button_map = json.load(config_file)
    return button_map


def fire_event(code, button_map):
    print("firing event for code: %s" % code)
    button_name = BUTTONS[code]
    print("button_name: %s" % button_name)

    if button_name not in button_map:
        print("Button %s not configured in magic_mapper_config.json " % button_name)
        return

    func_name = button_map[button_name]['function']
    print("func_name: %s" % func_name)
    inputs = button_map[button_name].get('inputs', {})
    globals()[func_name](inputs)


def luna_send(endpoint, payload):
    # Execute luna send and return the output

    command = ["/usr/bin/luna-send", "-n", "1"]
    command.append(endpoint)
    command.append(json.dumps(payload))
    print("running command: %s" % command)
    output = subprocess.check_output(command)
    return output


def cycle_energy_mode(inputs):
    # cycle energy modes between min med max off
    modes = ["max", "med", "min", "off"]
    if inputs.get('reverse_order'):
        modes.reverse()
    current_mode = get_picture_settings()["settings"]["energySaving"]

    if current_mode in modes:
        next_mode = modes.index(current_mode) + 1
    else:  # It's probably in auto mode so just start at the first mode
        next_mode = 0

    if next_mode >= len(modes):
        next_mode = 0

    inputs['mode'] = modes[next_mode]
    set_energy_mode(inputs)


def toggle_eye_comfort(inputs):
    """Toggle the eye comfort mode aka reduce blue light"""
    current_mode = get_picture_settings()["settings"]["eyeComfortMode"]
    print("current eye comfort mode: current_mode %s" % current_mode)
    if current_mode == "off":
        new_mode = "on"
    else:
        new_mode = "off"
    endpoint = "luna://com.webos.settingsservice/setSystemSettings"
    payload = {"category": "picture", "settings": {"eyeComfortMode": new_mode}}
    luna_send(endpoint, payload)
    if inputs.get('notifications'):
        show_message("Reduce blue light mode: %s" % new_mode)


def set_energy_mode(inputs):
    """Sets the energy savings mode"""
    mode = inputs['mode']
    endpoint = "luna://com.webos.settingsservice/setSystemSettings"
    payload = {"category": "picture", "settings": {"energySaving": mode}}
    luna_send(endpoint, payload)
    if inputs.get('notifications'):
        show_message("Energy mode: %s" % mode)


def increase_oled_light(inputs):
    increment_oled_light(inputs, direction='up')


def reduce_oled_light(inputs):
    increment_oled_light(inputs, direction='down')


def increment_oled_light(inputs, direction):
    increment = inputs.get('increment', 10)
    current_value = get_picture_settings()["settings"]["backlight"]

    if direction == 'up':
        new_value = current_value + increment
        if new_value > 100:
            new_value = 100
    elif direction == "down":
        new_value = current_value - increment
        if new_value < 0:
            new_value = 0

    inputs['backlight'] = new_value
    set_oled_backlight(inputs)


def set_oled_backlight(inputs):
    backlight = inputs['backlight']
    endpoint = "luna://com.webos.settingsservice/setSystemSettings"
    payload = {"category": "picture", "settings": {"backlight": backlight}}
    luna_send(endpoint, payload)
    if inputs.get('notifications'):
        show_message("OLED Backlight: %s" % backlight)


def get_picture_settings():
    # Return the current settings
    endpoint = "luna://com.webos.settingsservice/getSystemSettings"
    payload = {"category": "picture"}
    output = luna_send(endpoint, payload)
    settings = json.loads(output)
    return settings


def show_message(message):
    """Shows a "toast" message"""
    endpoint = "luna://com.webos.notification/createToast"
    payload = {"message": message}
    luna_send(endpoint, payload)


if __name__ == "__main__":
    main()