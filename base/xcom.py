#!/usr/bin/env python3.9

"""
xcom v.3.6.1 - July 2021
Author: colum31

A small terminal-type application to communicate via serial.
"""

# TODO: FIX
#       -fix cursor flashing
#       -optimize code (especially serial read)
#       -fix clearing process, when there is input
#       -fix !x behaviour after !h
#       -refactor code

# TODO: IMPLEMENT
#       -support for more special keys CTRL, DELETE, ESC ...
#       -mute feature
#       -log feature
#       -commmand history feature
#       -config files
#       -scripting with arduino firmware support

import threading
import queue
import time
import os
import serial
import subprocess
from nonblock import KBHit
from serialfunc import SerialFunc

d_port = '/dev/ttyS0'  # standart port
d_baud = 115200  # standart baud-rate


def print_get_zeilen():  # ueberprueft das terminal um zeilenzahl zu erhalten
    """Gibt zurueck, wie viele Zeilen es im Terminalfenster gibt."""

    p = (subprocess.check_output(["tput lines"], shell=True))
    return int(p)


def print_serial_info():  # druckt informationen ueber die verbindung
    """Gibt Informationen ueber die serielle Verbindung aus."""

    global print_queue
    global print_data_rdy_flag

    print_queue.put(("Nutze Port: {}\n\u001b[2KBaudrate betraegt {}".format(port, baud), "s", "SER_INFO"))
    print_data_rdy_flag.set()
    return


def print_clear():
    """Setzt das Terminalfenster zurueck."""

    os.system("tput clear")
    return


def print_read_keyboard(keyboard_queue):
    """Liest die Eingabe der Tastatur aus."""
    kb = KBHit()

    while True:
        if kb.kbhit():
            c = kb.getch()
            keyboard_queue.put(c)


def parse_input(erhalten):  # verarbeitet das eingelesene
    """Steuert den Programmablauf, mithilfe der ausgelesenen Daten der Tastatur."""

    global print_data_rdy_flag
    global send_data_flag
    global serial_send_queue
    global command_current_term
    global baud
    global port
    global ser
    global dateiname

    global ser_recv_thread_number
    global ser_send_thread_number
    global key_thread_number
    global main_thread_number

    if erhalten == "":
        print_queue.put(("Nichts gesendet!", "u"))
        return -1

    if erhalten[0] != '!' and ser.connected:
        serial_send_queue.put(erhalten + '\n')
        send_data_flag.set()
        return 0
    elif erhalten[0] == "!":
        befehl = erhalten.split()[0]

        if befehl == "!x":  # beende das Programm. Schliesse davor die Verbindung
            print_queue.put(("Beende Programm <3", "u"))
            return 1

        elif befehl == "!c":  # "cleare" das terminal
            print_queue.put(("", "RESET"))
            print_data_rdy_flag.set()
            return 2

        elif befehl == "!b":  # aendere baud-rate
            try:
                neue_baud = erhalten.split()[1]
            except IndexError:
                print_queue.put(("Baudrate angeben!", 'u'))
                print_data_rdy_flag.set()
                return 2

            if not neue_baud.isdigit():
                print_queue.put(("Baudrate {} ungueltig!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return 2

            neue_baud = int(neue_baud)

            if neue_baud > 4000000:
                print_queue.put(("Baudrate {} ist zu hoch!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return 2

            if neue_baud == baud:
                print_queue.put(("Baudrate {} ist bereits gesetzt!".format(neue_baud), 'u'))
                print_data_rdy_flag.set()
                return 2

            ser.change_baud(neue_baud)
            baud = neue_baud
            print_serial_info()
            print_queue.put(("Aendere Baud-Rate zu {}".format(neue_baud), 'i'))
            print_data_rdy_flag.set()
            return 2

        elif befehl == "!p":  # aendere port
            try:
                neuer_port = erhalten.split()[1]
            except IndexError:
                print_queue.put(("Port angeben!", 'u'))
                print_data_rdy_flag.set()
                return 2

            try:
                test_ser = serial.Serial(neuer_port, baud)

            except serial.SerialException:
                print_queue.put(("Keine serielle Verbindung unter Port {} moeglich".format(neuer_port), 'u'))
                print_data_rdy_flag.set()
                return 2

            test_ser.close()

            ser.change_port(neuer_port)
            port = neuer_port
            print_serial_info()
            print_queue.put(("Aendere Port zu {}".format(port), 'i'))
            print_data_rdy_flag.set()
            return 2

        elif befehl == "!d":  # debug: zeige Thread-Nummern an

            print_queue.put(("Main Thread hat Nummer: {}".format(main_thread_number), "i"))
            print_queue.put(("Serial Receive hat Nummer: {}".format(ser_recv_thread_number), "i"))
            print_queue.put(("Serial Send hat Nummer: {}".format(ser_send_thread_number), "i"))
            print_queue.put(("Keyboard Thread hat Nummer: {}".format(key_thread_number), "i"))
            print_queue.put(("Print Thread hat Nummer: {}".format(print_thread_number), "i"))
            print_data_rdy_flag.set()
            return 2

        elif befehl == "!h":  # Hangup: beeende Serielle Verbindung

            if not ser.connected:
                print_queue.put(("Nicht seriell verbunden: Beenden einer seriellen Verindung nicht moeglich!", "u"))
                return 2

            print_queue.put(("Beende Serielle Verbindung", "i"))
            ser.kill()
            print_queue.put(("Nutze Port: ----------\n\u001b[2KBaudrate betraegt ----------", "s", "SER_INFO"))
            return 2

        elif befehl == "!s":  # script: lese zu sendende daten aus datei aus

            try:

                dateiname = erhalten.split()[1]

            except IndexError:

                print_queue.put(("Dateiname angeben!", "u"))
                print_data_rdy_flag.set()
                return 2

            if os.path.isfile(dateiname):

                return 3
            else:

                print_queue.put(("Datei konnte nicht gefunden werden!", "u"))
                print_data_rdy_flag.set()
                return 2

        else:  # uengueltiger Befehl
            print_queue.put(("Ungueltiger Befehl", "u"))
            return 2

    return 2


def print_handle_keyboard(c):  # verarbeitet rohe daten von der tastatur
    """Verarbeitet Rohdaten der Tastatur."""
    global command_current_term
    global print_queue
    global print_data_rdy_flag

    if ord(c) == 127:  # DEL

        print_queue.put(("DEL", "kc"))
        print_data_rdy_flag.set()
        command_current_term = command_current_term[:-1]
        return 0

    if ord(c) == 10:  # ENTER
        print_queue.put(("ENTER", "kc"))
        print_data_rdy_flag.set()

        return 1

    command_current_term = command_current_term + str(c)
    print_queue.put((c, "k"))
    print_data_rdy_flag.set()

    return 0


def print_scroll():  # "scrollt" terminal text
    """Scrollt das Programmfenster."""
    print_clear()
    print_serial_info()
    return


def print_thread(stopflag, data_rdy, print_queue):
    """Gibt Text auf dem Terminalfenster aus."""

    zeilenanzahl = int(subprocess.check_output(["tput lines"], shell=True))
    command_zeile = zeilenanzahl - 4
    command_pos = 0
    meldung = False
    max_zeile = command_zeile - 3

    info = "[Info]: "
    raspberry = "\033[0;31m[Raspi]:\033[0m "
    arduino = "\033[1;34m[Arduino]:\033[0m "

    display_zeile = 4

    ser_info_string = ""
    while not stopflag.is_set():
        # hier NICHTS hin machen
        if data_rdy.wait():

            print_data = print_queue.get()

            if meldung:
                os.system("tput cup {} 0".format(command_zeile + 1))
                print("\u001b[2K", end='\r', flush=True)
                meldung = False

            if display_zeile >= max_zeile or print_data[1] == "RESET":
                os.system("tput clear")
                display_zeile = 4
                os.system("tput civis && tput cup 0 0")
                print(ser_info_string)

                continue

            if print_data[1] == "r":  # daten vom raspi

                os.system("tput civis && tput cup {} 0".format(display_zeile))
                display_zeile = display_zeile + 1

                print(raspberry + print_data[0], end="", flush=True)
                continue

            elif print_data[1] == "a":  # daten vom arduino drucken

                os.system("tput civis && tput cup {} 0".format(display_zeile))
                display_zeile = display_zeile + 1

                print(arduino + print_data[0], end="", flush=True)

                continue

            elif print_data[1] == "i":  # info daten in regularer zeile drucken

                os.system("tput civis && tput cup {} 0".format(display_zeile))
                display_zeile = display_zeile + 1

                print(info + print_data[0], end="", flush=True)

                continue

            elif print_data[1] == "u":  # info daten unter kommandozeile

                os.system("tput civis && tput cup {} 0".format(command_zeile + 1))
                print(print_data[0], end="", flush=True)
                meldung = True
                continue

            elif print_data[1] == "k":  # keyboard drucken

                os.system("tput cnorm && tput cup {} {}".format(command_zeile, command_pos))
                command_pos = command_pos + 1
                print(print_data[0], end="", flush=True)

                continue

            elif print_data[1] == "kc":  # keyboard kontrollsequenzen

                if print_data[0] == "ENTER":
                    os.system("tput cup {} {}".format(command_zeile, command_pos))
                    print("\u001b[2K", end='\r')
                    command_pos = 0
                    continue

                if print_data[0] == "DEL":

                    os.system("tput cup {} {}".format(command_zeile, command_pos))
                    if command_pos == 0:
                        continue
                    print('\b \b', end="", flush=True)
                    command_pos = command_pos - 1
                    continue

            elif print_data[1] == "s":  # serielle Info drucken

                if print_data[2] == "SER_INFO":
                    ser_info_string = str(print_data[0])
                    os.system("tput civis && tput cup 0 0")
                    print(ser_info_string, end="", flush=True)
                    continue
            if print_queue.qsize() == 0:
                os.system("tput cup {} {}".format(command_zeile, command_pos))
                data_rdy.clear()

    return 0


def script_reader(dateiname, q, send_flag):
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


# main

os.system("tput smcup")
print_clear()

zeilen = print_get_zeilen()  # zeilen des terminalfensters

port = d_port
baud = d_baud
dateiname = ""

command_current_term = ""  # alle eingegebenen zeichen

serial_send_thread = None
serial_recv_thread = None

serial_recv_queue = queue.Queue()
serial_send_queue = queue.Queue()
term_input_queue = queue.Queue()
print_queue = queue.Queue()

serial_kill_flag = threading.Event()
print_kill_flag = threading.Event()

print_data_rdy_flag = threading.Event()
send_data_flag = threading.Event()

ser = SerialFunc(port, baud, serial_kill_flag, send_data_flag, serial_recv_queue, serial_send_queue)

keyboardThread = threading.Thread(target=print_read_keyboard, args=(term_input_queue,), daemon=True)
keyboardThread.start()

printThread = threading.Thread(target=print_thread, args=(print_kill_flag, print_data_rdy_flag, print_queue,),
                               daemon=True)
printThread.start()

ser_recv_thread_number = 0
ser_send_thread_number = 0

key_thread_number = keyboardThread.native_id
main_thread_number = threading.get_native_id()
print_thread_number = printThread.native_id

print_serial_info()

while True:

    try:
        if serial_recv_queue.qsize() > 0:  # ueberprueft ob etwas empfangen wurde und stellt das dar

            serial_input = serial_recv_queue.get()
            print_queue.put((serial_input, "a"))
            print_data_rdy_flag.set()

        if term_input_queue.qsize() > 0:  # ueberprueft ob etwas eingegeben wurde

            c = term_input_queue.get()  # rohdaten
            term_return_code = print_handle_keyboard(c)  # handlen der rohdaten

            if term_return_code == 0:  # falls nicht enter gedrueckt wurde, normal weitermachen
                continue
            else:  # enter wurde gedrueeckt, verarbeitung des termes
                parse_code = parse_input(command_current_term)

            if parse_code == -1:  # nichts interesantes, ueberspringe schleifendurchgang

                continue

            if parse_code == 1:  # beende das programm
                ser.kill()  # beende serielle Verbindung

                print_kill_flag.set()  # beende den print-Thread
                print_data_rdy_flag.set()
                print_queue.put(("", "", ""))
                printThread.join()

                break
            if parse_code == 2:
                command_current_term = ""
                continue

            if parse_code == 3:
                script_reader(dateiname, serial_send_queue, send_data_flag)
                command_current_term = ""
                dateiname = ""
                continue

            print_queue.put((command_current_term, "r"))  # gibt das eingegebene aus und sendet es
            print_data_rdy_flag.set()
            command_current_term = ""  # resetet die zeichenkette

    except KeyboardInterrupt:  # beende programm bei ^C
        print("KeyboardInterrupt\n")
        break

    time.sleep(0.001)

ser.kill()
os.system("tput cnorm && tput rmcup")
