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

import serial
import threading
import queue
import time
import os

from printfunc import PrintFunc
from serialfunc import SerialFunc

d_port = '/dev/ttyS0'  # standart port
d_baud = 115200  # standart baud-rate


def parse_input(erhalten):  # verarbeitet das eingelesene
    """Steuert den Programmablauf, mithilfe der ausgelesenen Daten der Tastatur."""

    global mon
    global print_data_rdy_flag
    global send_data_flag
    global serial_send_queue
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
            mon.print_serial_info()
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
            mon.print_serial_info()
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

port = d_port
baud = d_baud
dateiname = ""


serial_send_thread = None
serial_recv_thread = None

serial_recv_queue = queue.Queue() # erstelle die Warteschlangen
serial_send_queue = queue.Queue()
term_input_queue = queue.Queue()
print_queue = queue.Queue()

serial_kill_flag = threading.Event() # erstelle die Flags
print_kill_flag = threading.Event()

print_data_rdy_flag = threading.Event()
send_data_flag = threading.Event()


ser = SerialFunc(port, baud, serial_kill_flag, send_data_flag, serial_recv_queue, serial_send_queue)
mon = PrintFunc(print_kill_flag, print_data_rdy_flag, term_input_queue ,print_queue, ser)


# speicher alle Nummern der Threads ab

ser_recv_thread_number = ser.recv_thread_n
ser_send_thread_number = ser.send_thread_n

key_thread_number = mon.keyboard_thread_n
print_thread_number = mon.print_thread_n

main_thread_number = threading.get_native_id()


while True:

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
                parse_code = parse_input(mon.cur)

            if parse_code == -1:  # nichts interesantes, ueberspringe schleifendurchgang

                continue

            if parse_code == 1:  # beende das programm

                ser.kill()
                mon.kill()
                break

            if parse_code == 2:
                mon.cur = ""
                continue

            if parse_code == 3:
                script_reader(dateiname, serial_send_queue, send_data_flag)
                mon.cur = ""
                dateiname = ""
                continue

            print_queue.put((mon.cur, "r"))  # gibt das eingegebene aus und sendet es
            print_data_rdy_flag.set()
            mon.cur = ""  # resetet die zeichenkette

    except KeyboardInterrupt:  # beende programm bei ^C
        print("KeyboardInterrupt\n")
        break

    time.sleep(0.001)

ser.kill()
mon.restore_screen()
