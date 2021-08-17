import threading
import os
import subprocess
from xcom.nonblock import KBHit


class PrintFunc:
    """Implementiert die Ein- und Ausgabe auf dem Terminalfenster."""

    def __init__(self, killflag, printflag, keyboard_queue, print_queue, ser, wake_main, profile):
        """Standart Konstruktor. Initialisiert Objekt und startet Thread."""

        self.zeilen = self._get_zeilen()
        self.reihen = self._get_reihen()
        self.command_pos = 0

        self.infostring = ""
        self.this_device_string = ""
        self.other_device_string = ""

        self.profile = profile

        self.set_strings(self.profile)

        self.killflag = killflag
        self.printflag = printflag
        self.print_queue = print_queue
        self.keystroke_queue = keyboard_queue
        self.ser = ser
        self.cur = ""
        self.wake_main = wake_main

        self.keyboard_thread = None
        self.print_thread = None

        self.keyboard_thread_n = 0
        self.print_thread_n = 0

        self.save_screen()
        self._start_threads()
        self.print_clear()
        self.print_serial_info()

    def _start_threads(self):
        """Startet Threads, um die Tastatur zu lesen und auf dem Bildschirm zu schreiben."""

        keythread = threading.Thread(target=self._read_keyboard, args=(self.keystroke_queue,), daemon=True)
        keythread.start()
        self.keyboard_thread = keythread

        printthread = threading.Thread(target=self._term_print, args=(self.killflag, self.printflag, self.print_queue,),
                                       daemon=True)
        printthread.start()
        self.print_thread = printthread

        self.keyboard_thread_n = keythread.native_id
        self.print_thread_n = printthread.native_id

    def set_strings(self, profile):
        """Wecheselt die Profileinstellungen."""

        self.profile = profile

        self.infostring = "[Info]: "
        self.this_device_string = "\033[{}{}[{}]:\033[0m ".format(profile.this_boldness, profile.this_color,
                                                                  profile.this_device)
        self.other_device_string = "\033[{}{}[{}]:\033[0m ".format(profile.other_boldness, profile.other_color,
                                                                   profile.other_device)

    def kill(self):
        """Beendet die Threads."""
        self.killflag.set()

        self.print_queue.put(("", "", ""))
        self.printflag.set()
        self.print_thread.join()

    def save_screen(self):
        """Sichert den aktuellen Zustand des Terminalfensters."""

        os.system("tput smcup")

    def restore_screen(self):
        """Stellt den gesicherten Zustand des Terminals wieder her."""

        os.system("tput cnorm && tput rmcup")

    def _get_zeilen(self):  # ueberprueft das terminal um zeilenzahl zu erhalten
        """Gibt zurueck, wie viele Zeilen es im Terminalfenster gibt."""

        p = (subprocess.check_output(["tput lines"], shell=True))
        return int(p)

    def _get_reihen(self):
        """Gibt zurueck, wie viele Reihen es im Terminalfenster gibt."""

        p = (subprocess.check_output(["tput cols"], shell=True))
        return int(p)

    def print_serial_info(self):  # druckt informationen ueber die verbindung
        """Gibt Informationen ueber die serielle Verbindung aus."""

        if self.ser.connected:
            self.print_queue.put(("Nutze Port: {}\n\u001b[2KBaudrate betraegt {}".format(self.ser.port, self.ser.baud),
                                  "s", "SER_INFO"))
            self.printflag.set()

        else:
            self.print_queue.put(("Nutze Port: ----------\n\u001b[2KBaudrate betraegt ----------", "s", "SER_INFO"))
            self.printflag.set()
        return

    def print_clear(self):
        """Setzt das Terminalfenster zurueck."""

        os.system("tput clear")
        return

    def _read_keyboard(self, keyboard_queue):
        """Liest die Eingabe der Tastatur aus."""
        kb = KBHit()

        while True:
            if kb.kbhit():
                c = kb.getch()
                keyboard_queue.put(c)
                self.wake_main.set()

    def handle_keyboard(self, c):  # verarbeitet rohe daten von der tastatur
        """Verarbeitet Rohdaten der Tastatur."""

        if ord(c) == 127:  # DEL

            self.print_queue.put(("DEL", "kc"))
            self.printflag.set()
            self.cur = self.cur[:-1]
            return 0

        if ord(c) == 10:  # ENTER
            self.print_queue.put(("ENTER", "kc"))
            self.printflag.set()

            return 1

        self.cur = self.cur + str(c)
        self.print_queue.put((c, "k"))
        self.printflag.set()

        return 0

    def scroll(self):  # "scrollt" terminal text
        """Scrollt das Programmfenster."""
        self.print_clear()
        self.print_serial_info()

        self.command_pos = 0

        if self.cur != "":
            self.print_queue.put((self.cur, "kp"))
            self.printflag.set()

        return

    def _term_print(self, stopflag, data_rdy, print_queue):
        """Gibt Text auf dem Terminalfenster aus."""

        zeilenanzahl = self.zeilen
        command_zeile = zeilenanzahl - 4
        meldung = False
        max_zeile = command_zeile - 3

        display_zeile = 4

        while not stopflag.is_set():
            # hier NICHTS hin machen
            if data_rdy.wait():

                print_data = print_queue.get()

                if meldung:
                    os.system("tput cup {} 0".format(command_zeile + 1))
                    print("\u001b[2K", end='\r', flush=True)
                    meldung = False

                if display_zeile >= max_zeile or print_data[1] == "RESET":
                    display_zeile = 4
                    self.scroll()

                    continue

                if print_data[1] == "r":  # daten vom raspi

                    os.system("tput civis && tput cup {} 0".format(display_zeile))
                    display_zeile = display_zeile + 1

                    print(self.this_device_string + print_data[0], end="", flush=True)
                    continue

                elif print_data[1] == "a":  # daten vom arduino drucken

                    os.system("tput civis && tput cup {} 0".format(display_zeile))
                    display_zeile = display_zeile + 1

                    print(self.other_device_string + print_data[0], end="", flush=True)

                    continue

                elif print_data[1] == "i":  # info daten in regularer zeile drucken

                    os.system("tput civis && tput cup {} 0".format(display_zeile))
                    display_zeile = display_zeile + 1

                    print(self.infostring + print_data[0], end="", flush=True)

                    continue

                elif print_data[1] == "u":  # info daten unter kommandozeile

                    os.system("tput civis && tput cup {} 0".format(command_zeile + 1))
                    print(print_data[0], end="", flush=True)
                    meldung = True

                    continue

                elif print_data[1] == "k":  # keyboard drucken

                    os.system("tput cnorm && tput cup {} {}".format(command_zeile, self.command_pos))
                    self.command_pos = self.command_pos + 1
                    print(print_data[0], end="", flush=True)

                    continue

                elif print_data[1] == "kp":  # key-paste - fuege mehrere zeichen gleichzeitig ein

                    os.system("tput cnorm && tput cup {} {}".format(command_zeile, self.command_pos))
                    self.command_pos = self.command_pos + len(print_data[0])
                    print(print_data[0], end="", flush=True)

                    continue

                elif print_data[1] == "kc":  # keyboard kontrollsequenzen

                    if print_data[0] == "ENTER":
                        os.system("tput cup {} {}".format(command_zeile, self.command_pos))
                        print("\u001b[2K", end='\r')
                        self.command_pos = 0

                        continue

                    if print_data[0] == "DEL":

                        os.system("tput cup {} {}".format(command_zeile, self.command_pos))
                        if self.command_pos == 0:
                            continue
                        print('\b \b', end="", flush=True)
                        self.command_pos = self.command_pos - 1
                        continue

                elif print_data[1] == "s":  # serielle Info drucken

                    if print_data[2] == "SER_INFO":
                        ser_info_string = str(print_data[0])
                        os.system("tput civis && tput cup 0 0")
                        print(ser_info_string, end="", flush=True)
                        continue
                if print_queue.qsize() == 0:
                    os.system("tput cup {} {}".format(command_zeile, self.command_pos))
                    data_rdy.clear()

            return 0
