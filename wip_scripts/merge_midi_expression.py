# /// script
# requires-python = "~=3.12.0"
# dependencies = [
#     "ducktools-classbuilder",
#     "mido[ports-rtmidi]",
# ]
# ///
import sys
from math import ceil

import mido

from ducktools.classbuilder.prefab import Prefab

SEABOARD_NAME = "Seaboard BLOCK M"
EXPRESSION_NAME = "MIDI4x4 Midi In 3"  # Kurzweil with expression pedal
VIRTUAL_DEVICE_NAME = "Virtual Seaboard"

EXPRESSION_CC = 11
BRIGHTNESS_CC = 74


def check_inputs(midi_inputs: list[str]) -> bool:
    known_inputs = mido.get_input_names()  # type: ignore

    return all(name in known_inputs for name in midi_inputs)


class MidiModifier(Prefab):
    """
    This class takes two midi sources by name.

    main_source is the source for notes and all CC messages
    expression_source is the source for a separate expression pedal

    While active this takes the last known value of the expression source
    and uses it to "compress" the values of pressure from the main_source.
    This is done by raising the floor value of the pressure messages and 
    adjusting the in-between values accordingly.
    """
    main_source: str
    expression_source: str
    virtual_device: str = VIRTUAL_DEVICE_NAME

    max_expression: int = 64

    filter_sysex: bool = True  # The seaboard sends a bunch of sysex I want to filter

    @staticmethod
    def __prefab_pre_init__(main_source, expression_source):
        known_inputs = mido.get_input_names()  # type: ignore

        for device in (main_source, expression_source):
            if device not in known_inputs:
                raise RuntimeError(f"{device!r} input is not enabled")
    
    def print_messages(self) -> None:
        # A simple print function to show the outputs
        with mido.open_input(self.main_source) as main, mido.open_input(self.expression_source) as expr:  # type: ignore
            try:
                for pair in mido.ports.multi_receive([main, expr], yield_ports=True):
                    device, message = pair

                    if self.filter_sysex and message.type == "sysex":
                        continue
    
                    if device.name == self.main_source and message.type == "aftertouch":
                        print(device.name, message)
                    elif device.name == self.expression_source and message.is_cc(11):
                        print(device.name, message)

            except KeyboardInterrupt:
                pass

    def start_virtual_aftertouch(self) -> None:
        """
        Start the virtual device, relaying main_source with only aftertouch values altered per channel
        """
        last_expression = 0
        scaling = self.max_expression / 128  # 128 so 64 is exactly half
        last_pressures = {} # Last pressure messages for each channel before scaling
        expression_cc = EXPRESSION_CC
        brightness_cc = BRIGHTNESS_CC

        print(f"Starting virtual device with scaling: {scaling} - Pressure Mode")
        print("Press ctrl + c to close")
        with mido.open_output(self.virtual_device, virtual=True) as midi_out:  # type: ignore
            with mido.open_input(self.main_source) as main, mido.open_input(self.expression_source) as expr:  # type: ignore
                try:
                    for pair in mido.ports.multi_receive([main, expr], yield_ports=True):
                        device, message = pair
                        if self.filter_sysex and message.type == "sysex":
                            continue

                        if device.name == self.expression_source:
                            if message.is_cc(expression_cc):
                                last_expression = message.value
                                for pressure in last_pressures.values():
                                    new_value = ceil(pressure.value * (1 - (last_expression/127 * scaling)) + last_expression * scaling)
                                    new_message = pressure.copy(value=new_value)
                                    midi_out.send(new_message)
                                
                        else:  # Must be main_source, no need to check
                            if message.type == "aftertouch":
                                # Aftertouch scaling calculation
                                new_value = ceil(message.value * (1 - (last_expression/127 * scaling)) + last_expression * scaling)
                                last_pressures[message.channel] = message
                                new_message = message.copy(value=new_value)
                                midi_out.send(new_message)
                            else:
                                midi_out.send(message)
                                if message.type == "note_on":  # Hack for Studio One 5
                                    # Send a brightness reset for Studio One which sets it to 0 on note on for some reason?
                                    # So we send a default value *after* the initial note to keep it at the midpoint
                                    brightness = mido.Message("control_change", channel=message.channel, control=brightness_cc, value=64)
                                    midi_out.send(brightness)

                except KeyboardInterrupt:
                    pass
        
        print("Closing")

    def start_virtual_expression(self) -> None:
        """
        Start the virtual device, relaying main_source with expression values
        """
        # localise variables
        expression_cc = EXPRESSION_CC
        brightness_cc = BRIGHTNESS_CC

        last_expression = mido.Message("control_change", control=expression_cc, channel=0, value=0)  # type: ignore

        scaling = self.max_expression / 128  # 128 so 64 is exactly half
        last_pressure = 0 # Last pressure message before scaling

        print(f"Starting virtual device with scaling: {scaling} - Expression Mode")
        print("Press ctrl + c to close")
        with mido.open_output(self.virtual_device, virtual=True) as midi_out:  # type: ignore
            with mido.open_input(self.main_source) as main, mido.open_input(self.expression_source) as expr:  # type: ignore
                try:
                    for pair in mido.ports.multi_receive([main, expr], yield_ports=True):
                        device, message = pair  # type: ignore
                        
                        if self.filter_sysex and message.type == "sysex":
                            continue

                        if device.name == self.expression_source:
                            if message.is_cc(expression_cc):
                                last_expression = message
                                
                                new_value = ceil(last_pressure * (1 - (last_expression.value/127 * scaling)) + last_expression.value * scaling)  # type: ignore
                                new_message = message.copy(value=new_value)
                                midi_out.send(new_message)
                                
                        else:  # Must be main_source, no need to check
                            if message.type == "aftertouch":
                                last_pressure = message.value

                                # Aftertouch scaling calculation
                                new_value = ceil(message.value * (1 - (last_expression.value/127 * scaling)) + last_expression.value * scaling)  # type: ignore
                                
                                # Send it out as a new expression value
                                new_message = last_expression.copy(value=new_value)
                                midi_out.send(new_message)
                            else:
                                midi_out.send(message)
                                if message.type == "note_on":  # Hack for Studio One 5
                                    # Send a brightness reset for Studio One which sets it to 0 on note on for some reason?
                                    # So we send a default value *after* the initial note to keep it at the midpoint
                                    brightness = mido.Message("control_change", channel=message.channel, control=brightness_cc, value=64)
                                    midi_out.send(brightness)

                except KeyboardInterrupt:
                    pass
        
        print("Closing")


def main() -> int:
    
    modifier = MidiModifier(SEABOARD_NAME, EXPRESSION_NAME)
    modifier.start_virtual_expression()

    return 0


if __name__ == "__main__":
    sys.exit(main())
