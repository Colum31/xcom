import threading
import os
import subprocess
from nonblock import KBHit


class PrintFunc:
    """Implementiert die Ein- und Ausgabe auf dem Terminalfenster."""

    def __init__(self, killflag, printflag, keyboard_queue, print_queue, ser):
        """Standart Konstruktor. Initialisiert Objekt und startet Thread."""

        self.zeilen = self.get_zeilen()
        self.killflag = killflag
        self.printflag = printflag
        self.print_queue = print_queue
        self.keystroke_queue = keyboard_queue
        self.ser = ser
        self.cur = ""

        self.keyboard_thread = None
        self.print_thread = None

        self.keyboard_thread_n = 0
        self.print_thread_n = 0

        self.save_screen()
        self.start_threads()
        self.print_clear()
        self.print_serial_info()

    def start_threads(self):
        """Startet Threads, um die Tastatur zu lesen und auf dem Bildschirm zu schreiben."""

        keythread = threading.Thread(target=self.read_keyboard, args=(self.keystroke_queue,), daemon=True)
        keythread.start()
        self.keyboard_thread = keythread

        printthread = threading.Thread(target=self.term_print, args=(self.killflag, self.printflag, self.print_queue,),
                                       daemon=True)
        printthread.start()
        self.print_thread = printthread

        self.keyboard_thread_n = keythread.native_id
        self.print_thread_n = printthread.native_id

    def kill(self):
        """Beendet die Threads."""
        self.killflag.set()

        self.print_queue.put(("", "", ""))
        self.printflag.set()
        self.print_thread.join()


    def save_screen(self):
        "Sichert den aktuellen Zustand des Terminalfensters."

        os.system("tput smcup")

    def restore_screen(self):
        "Stellt den gesicherten Zustand des Terminals wieder her."

        os.system("tput cnorm && tput rmcup")

    def get_zeilen(self):  # ueberprueft das terminal um zeilenzahl zu erhalten
        """Gibt zurueck, wie viele Zeilen es im Terminalfenster gibt."""

        p = (subprocess.check_output(["tput lines"], shell=True))
        return int(p)

    def print_serial_info(self):  # druckt informationen ueber die verbindung
        """Gibt Informationen ueber die serielle Verbindung aus."""

        self.print_queue.put(("Nutze Port: {}\n\u001b[2KBaudrate betraegt {}".format(self.ser.port, self.ser.baud), "s", "SER_INFO"))
        self.printflag.set()
        return

    def print_clear(self):
        """Setzt das Terminalfenster zurueck."""

        os.system("tput clear")
        return

    def read_keyboard(self, keyboard_queue):
        """Liest die Eingabe der Tastatur aus."""
        kb = KBHit()

        while True:
            if kb.kbhit():
                c = kb.getch()
                keyboard_queue.put(c)

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
        return

    def term_print(self, stopflag, data_rdy, print_queue):
        """Gibt Text auf dem Terminalfenster aus."""

        zeilenanzahl = self.zeilen
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
