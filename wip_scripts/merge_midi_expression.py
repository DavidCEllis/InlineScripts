# /// script
# requires-python = "~=3.12.0"
# dependencies = [
#     "ducktools-classbuilder~=0.10.0",
#     "mido[ports-rtmidi]~=1.3.3",
# ]
# ///
"""
This script is intended to create a virtual MIDI device that combines the 
aftertouch of an MPE instrument such as the Seaboard that has no expression
pedal input, with the expression input from another MIDI device.

The expression pedal is used to set a minimum value for aftertouch input.
Aftertouch from the MPE device is then rescaled to go from this new minimum
to the maximum of 127.

This will need modification to work on Windows as mido is unable to create a
virtual port on that platform.
See: https://mido.readthedocs.io/en/latest/backends/rtmidi.html#virtual-ports
"""
import sys
import argparse
from math import ceil

import mido

from ducktools.classbuilder.prefab import Prefab

# When run directly as a script these are the device names that will be used
VIRTUAL_DEVICE_NAME = "Virtual Seaboard"
MPE_DEVICE_NAME = "Seaboard BLOCK M"
EXPRESSION_DEVICE_NAME = "MIDI4x4 Midi In 3"  # Name of the device with the expression pedal

EXPRESSION_CC = 11
MAX_EXPRESSION = 64


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

    :param main_source: The name of your main MPE device
    :param expression_source: The name of the MIDI device to take Expression input from
    :param virtual_device: The name of the new virtual device to create
    :param max_expression: The value that the expression pedal at maximum level sets as 
                           the minimum aftertouch value
    :param filter_sysex: Remove sysex messages from the midi output of the virtual device
    """
    virtual_device: str
    main_source: str
    expression_source: str

    expression_cc: int
    max_expression: int
    filter_sysex: bool = True

    @staticmethod
    def __prefab_pre_init__(main_source, expression_source):
        """
        Check to make sure both named devices are currently available
        """
        known_inputs = mido.get_input_names()  # type: ignore

        for device in (main_source, expression_source):
            if device not in known_inputs:
                raise RuntimeError(f"{device!r} input is not enabled")
    
    def print_messages(self) -> None:
        """
        Simple print function to show the source aftertouch and expression values.
        """

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

        # Need to keep track of the last pressure values for each channel before scaling
        # When the expression pedal is moved it will send new re-scaled aftertouch messages
        # for every channel.
        last_pressures = {}

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
                            # If expression is changed, send out updates for *all* aftertouch values with new scaling
                            if message.is_cc(self.expression_cc):
                                last_expression = message.value
                                for pressure in last_pressures.values():
                                    new_value = ceil(pressure.value * (1 - (last_expression/127 * scaling)) + last_expression * scaling)
                                    new_message = pressure.copy(value=new_value)
                                    midi_out.send(new_message)
                                
                        else:  # Must be main_source, no need to check device name
                            if message.type == "aftertouch":
                                # Store unscaled aftertouch values
                                last_pressures[message.channel] = message

                                # Aftertouch scaling calculation
                                new_value = ceil(message.value * (1 - (last_expression/127 * scaling)) + last_expression * scaling)
                                new_message = message.copy(value=new_value)
                                midi_out.send(new_message)
                            else:
                                # Non-aftertouch messages sent unaltered
                                midi_out.send(message)

                except KeyboardInterrupt:
                    pass
        
        print("Closing")


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-devices", action="store_true")
    return parser


def main() -> int:
    if len(sys.argv) > 1:
        parser = get_parser()
        args = parser.parse_args()
        if args.list_devices:
            print("Valid MIDI input device names:")
            for item in mido.get_input_names():
                print(f"\t{item!r}")
            return 0

    modifier = MidiModifier(
        virtual_device=VIRTUAL_DEVICE_NAME,
        main_source=MPE_DEVICE_NAME, 
        expression_source=EXPRESSION_DEVICE_NAME,
        expression_cc=EXPRESSION_CC,
        max_expression=MAX_EXPRESSION,
        filter_sysex=True,
    )
    modifier.start_virtual_aftertouch()

    return 0


if __name__ == "__main__":
    sys.exit(main())
