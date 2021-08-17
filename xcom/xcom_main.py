#!/usr/bin/env python3.9

"""
xcom v.3.9 - August 2021
Author: Colum31

A small terminal-type application to communicate via serial.
"""

# TODO: FIX
#       -fix cursor flashing
#       -fix !x behaviour after !h

# TODO: IMPLEMENT
#       -support for more special keys CTRL, DELETE, ESC ...
#       -mute feature
#       -log feature
#       -command history feature
#       -scripting with arduino firmware support

import serial
import threading
import queue
import time
import os
import json

from xcom.printfunc import PrintFunc
from xcom.serialfunc import SerialFunc

d_port = '/dev/ttyS0'  # standart port
d_baud = 115200  # standart baud-rate

d_this_name = "Raspi"
d_other_name = "Arduino"

MAX_BAUD = 4000000
profile_list = list()


class ParseCodes:
    """Stellt enums fuer Rueckgabewerte bereit."""
    SKIP = -1
    SEND = 0
    QUIT = 1
    CLEAR = 2
    SCRIPT = 3


class Profile:
    """Speichert die Daten fuer Profile."""
    name = ""

    this_device = ""
    other_device = ""

    this_color = None
    this_boldness = 0
    other_color = None
    other_boldness = 0

    baud = 0
    port = 0


Colors = {
    
    "BLACK":    ";30m",
    "RED":      ";31m",
    "GREEN":    ";32m",
    "YELLOW":   ";33m",
    "BLUE":     ";34m",
    "PURPLE":   ";35m",
    "CYAN":     ";36m",
    "WHITE":    ";37m"

}


def make_default_profile():
    """Erstellt ein Profil mit Standarteinstellungen."""

    entry_default = Profile()
    entry_default.name = "default"
    entry_default.port = d_port
    entry_default.baud = d_baud

    entry_default.this_device = d_this_name
    entry_default.this_color = Colors.get("RED")
    entry_default.this_boldness = 1

    entry_default.other_device = d_other_name
    entry_default.other_color = Colors.get("BLUE")
    entry_default.other_boldness = 1

    profile_list.append(entry_default)


def parse_config():
    """Lade lokale oder globale Konfigurationsdatei."""

    global profile_list

    configfile = None
    # suche als erstes im lokalen Ordner

    try:
        configfile = open("config.json", "r")
        datei = True
    except IOError:
        datei = False

    # wenn nichts gefunden wurde, suche im home-directory weiter

    if not datei:
        try:
            configfile = open("{}/.xcom/config.json".format(os.path.expanduser('~')), "r")
        except IOError:
            return 0

    try:
        data = json.load(configfile)
    except json.decoder.JSONDecodeError:
        return 0

    configfile.close()

    # fuege alle Profile der Liste hinzu, wenn keine da, gebe nichts zurueck

    try:
        for i in data["profiles"]:
            entry = Profile()
            entry.name = i.get("profile-name")
            entry.port = i.get("port")
            entry.baud = i.get("baudrate")
            entry.this_device = i.get("this-name")
            entry.other_device = i.get("other-name")

            entry.this_color = Colors.get(i.get("this-color"))
            entry.other_color = Colors.get(i.get("other-color"))

            entry.other_boldness = i.get("other-boldness")
            entry.this_boldness = i.get("this-boldness")

            profile_list.append(entry)

    except KeyError:
        return 0

    return len(profile_list)


def print_config_name(name):
    """Gibt den aktuellen Profilnamen aus."""
    if name is None:
        return

    print_queue.put(("Nutze Profil: {}".format(name.name), "u"))
    print_data_rdy_flag.set()


def parse_input(erhalten, ser, mon, send_data_flag, serial_send_queue):  # verarbeitet das eingelesene
    """Steuert den Programmablauf, mithilfe der ausgelesenen Daten der Tastatur."""

    global dateiname
    global print_queue
    global print_data_rdy_flag

    if erhalten == "":
        print_queue.put(("Nichts gesendet!", "u"))
        return ParseCodes.SKIP

    if erhalten[0] != '!' and ser.connected:
        serial_send_queue.put(erhalten + '\n')
        send_data_flag.set()
        return ParseCodes.SEND

    elif erhalten[0] == "!":
        befehl = erhalten.split()[0]

        if befehl == "!x":  # beende das Programm. Schliesse davor die Verbindung
            print_queue.put(("Beende Programm <3", "u"))
            return ParseCodes.QUIT

        elif befehl == "!c":  # "cleare" das terminal
            print_queue.put(("", "RESET"))
            print_data_rdy_flag.set()
            return ParseCodes.CLEAR

        elif befehl == "!b":  # aendere baud-rate
            try:
                neue_baud = erhalten.split()[1]
            except IndexError:
                print_queue.put(("Baudrate angeben!", 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            if not neue_baud.isdigit():
                print_queue.put(("Baudrate \"{}\" ungueltig!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            neue_baud = int(neue_baud)

            if neue_baud > MAX_BAUD:
                print_queue.put(("Baudrate \"{}\" ist zu hoch!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            if neue_baud == ser.baud:
                print_queue.put(("Baudrate \"{}\" ist bereits gesetzt!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            ser.change_baud(neue_baud)
            mon.print_serial_info()
            get_serial_thread_numbers(ser)
            print_queue.put(("Aendere Baud-Rate zu \"{}\"".format(neue_baud), 'i'))
            print_data_rdy_flag.set()
            return ParseCodes.CLEAR

        elif befehl == "!p":  # aendere port
            try:
                neuer_port = erhalten.split()[1]
            except IndexError:
                print_queue.put(("Port angeben!", 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            try:
                test_ser = serial.Serial(neuer_port, ser.baud)

            except serial.SerialException:
                print_queue.put(("Keine serielle Verbindung unter Port \"{}\" moeglich".format(neuer_port), 'u'))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            test_ser.close()

            ser.change_port(neuer_port)
            port = neuer_port
            mon.print_serial_info()
            get_serial_thread_numbers(ser)
            print_queue.put(("Aendere Port zu \"{}\"".format(port), 'i'))
            print_data_rdy_flag.set()
            return ParseCodes.CLEAR

        elif befehl == "!pr":  # aendere Profil

            try:
                profilename = erhalten.split()[1]
            except IndexError:
                print_queue.put(("Profilnamen angeben!", "u"))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            # pruefe ob Profil in Liste vorhanden
            for i in profile_list:
                if i.name == profilename:
                    ser.kill()
                    ser.init(i.port, i.baud)

                    if not ser.connected:
                        mon.print_serial_info()
                        print_queue.put(("Verbindung mit Daten aus Profil {} nicht moeglich!".format(profilename), "u"))
                        return ParseCodes.CLEAR

                    print_config_name(i)
                    mon.set_strings(i)
                    mon.print_serial_info()
                    return ParseCodes.CLEAR

            # wenn nicht, gib Fehlermeldung aus
            print_queue.put(("Konnte kein Profil \"{}\" finden!".format(profilename), "u"))
            print_data_rdy_flag.set()
            return ParseCodes.CLEAR

        elif befehl == "!d":  # debug: zeige Thread-Nummern an

            print_threadnumbers()
            return ParseCodes.CLEAR

        elif befehl == "!h":  # Hangup: beeende Serielle Verbindung

            if not ser.connected:
                print_queue.put(("Nicht seriell verbunden: Beenden einer seriellen Verindung nicht moeglich!", "u"))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            print_queue.put(("Beende Serielle Verbindung", "i"))
            print_data_rdy_flag.set()
            ser.kill()
            mon.print_serial_info()
            print_data_rdy_flag.set()
            get_serial_thread_numbers(ser)
            return ParseCodes.CLEAR

        elif befehl == "!s":  # script: lese zu sendende daten aus datei aus

            try:

                script_dateiname = erhalten.split()[1]

            except IndexError:

                print_queue.put(("Dateiname angeben!", "u"))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

            if os.path.isfile(script_dateiname):

                dateiname = script_dateiname
                return ParseCodes.SCRIPT
            else:

                print_queue.put(("Datei \"{}\" konnte nicht gefunden werden!".format(script_dateiname), "u"))
                print_data_rdy_flag.set()
                return ParseCodes.CLEAR

        else:  # uengueltiger Befehl
            print_queue.put(("Ungueltiger Befehl \"{}\"".format(erhalten), "u"))
            return ParseCodes.CLEAR

    return ParseCodes.CLEAR


def print_threadnumbers():
    """Gibt die Threadnummern der Threads aus."""

    print_queue.put(("Main Thread hat Nummer: {}".format(main_thread_number), "i"))
    print_queue.put(("Serial Receive hat Nummer: {}".format(ser_recv_thread_number), "i"))
    print_queue.put(("Serial Send hat Nummer: {}".format(ser_send_thread_number), "i"))
    print_queue.put(("Keyboard Thread hat Nummer: {}".format(key_thread_number), "i"))
    print_queue.put(("Print Thread hat Nummer: {}".format(print_thread_number), "i"))
    print_queue.put(("Debug mit: top -H -p {}".format(main_thread_number), "i"))
    print_data_rdy_flag.set()


def get_serial_thread_numbers(ser):
    """Aktualisiert die Thread Nummern"""
    global ser_recv_thread_number
    global ser_send_thread_number

    ser_recv_thread_number = ser.recv_thread_n
    ser_send_thread_number = ser.send_thread_n


def script_reader(q, send_flag):
    """Versendet Daten aus einer Datei seriell."""

    delay = 0
    delay_da = False

    with open(dateiname, "r") as datei:  # skript oeffnen

        for line in datei:  # suche als erstes die delay option

            try:
                if line.split()[0] == "DELAY":
                    delay = line.split()[1]
                    delay_da = True
                    break
            except IndexError:
                pass

        if delay_da:  # wenn es die delay option gibt, warte n ms ab zwischen den kommandos
            for line in datei:
                q.put(line)
                time.sleep(int(delay) / 1000)
                send_flag.set()

        if not delay_da:  # wenn nicht, dann nicht
            datei.seek(0)
            for line in datei:
                q.put(line)
                send_flag.set()

        return 0


main_thread_number = 0
ser_recv_thread_number = 0
ser_send_thread_number = 0
key_thread_number = 0
print_thread_number = 0

dateiname = ""

print_queue = queue.Queue()
print_data_rdy_flag = threading.Event()


def main():
    """Hauptprogramm. Fuehrt das Terminal aus"""

    global key_thread_number
    global main_thread_number
    global print_thread_number

    serial_recv_queue = queue.Queue()  # erstelle die Warteschlangen
    serial_send_queue = queue.Queue()
    term_input_queue = queue.Queue()

    serial_kill_flag = threading.Event()  # erstelle die Flags
    print_kill_flag = threading.Event()

    main_event_flag = threading.Event()
    send_data_flag = threading.Event()

    make_default_profile()
    parse_config()

    profile = profile_list[-1]
    port = profile.port
    baud = profile.baud

    ser = SerialFunc(port, baud, serial_kill_flag, send_data_flag, serial_recv_queue, serial_send_queue,
                     main_event_flag)
    mon = PrintFunc(print_kill_flag, print_data_rdy_flag, term_input_queue, print_queue, ser, main_event_flag, profile)

    if not ser.connected:
        print_queue.put(("Konnte keine Verbindung zum Port \"{}\" oeffnen!".format(port), "u"))
        print_data_rdy_flag.set()

    # speicher alle Nummern der Threads ab

    get_serial_thread_numbers(ser)

    key_thread_number = mon.keyboard_thread_n
    print_thread_number = mon.print_thread_n

    main_thread_number = threading.get_native_id()
    main_event_flag.clear()

    print_config_name(profile)

    while True:

        main_event_flag.wait()
        main_event_flag.clear()
        try:
            if serial_recv_queue.qsize() > 0:  # ueberprueft ob etwas empfangen wurde und stellt das dar

                serial_input = serial_recv_queue.get()
                print_queue.put((serial_input, "a"))
                print_data_rdy_flag.set()

            if term_input_queue.qsize() > 0:  # ueberprueft ob etwas eingegeben wurde

                c = term_input_queue.get()  # rohdaten
                term_return_code = mon.handle_keyboard(c)  # handlen der rohdaten

                if term_return_code == 0:  # falls nicht enter gedrueckt wurde, normal weitermachen
                    continue
                else:  # enter wurde gedrueeckt, verarbeitung des termes
                    parse_code = parse_input(mon.cur, ser, mon, send_data_flag, serial_send_queue)

                if parse_code == ParseCodes.SKIP:  # nichts interesantes, ueberspringe schleifendurchgang

                    continue

                if parse_code == ParseCodes.QUIT:  # beende das programm

                    ser.kill()
                    mon.kill()
                    break

                if parse_code == ParseCodes.CLEAR:
                    mon.cur = ""
                    continue

                if parse_code == ParseCodes.SCRIPT:
                    script_reader(serial_send_queue, send_data_flag)
                    mon.cur = ""
                    continue

                print_queue.put((mon.cur, "r"))  # gibt das eingegebene aus und sendet es
                print_data_rdy_flag.set()
                mon.cur = ""  # resetet die zeichenkette

        except KeyboardInterrupt:  # beende programm bei ^C
            print("KeyboardInterrupt\n")
            break

        time.sleep(0.001)

    mon.restore_screen()


if __name__ == "__main__":
    main()
