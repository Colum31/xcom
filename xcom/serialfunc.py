import queue
import serial
import threading


class SerialFunc:
    """Implementiert serielle Funktionalitaet."""

    def __init__(self, port, baud, killflag, dataflag, recv_queue, send_queue, wake_main):
        """Standart Konstruktor."""

        # alles wird auf standart werte gesetzt, wenn Wert noch nicht bekannt

        self.port = port
        self.baud = baud

        self.killflag = killflag
        self.dataflag = dataflag

        self.recv_queue = recv_queue
        self.send_queue = send_queue

        self.recv_thread = None
        self.send_thread = None

        self.connected = False

        self.recv_thread_n = 0
        self.send_thread_n = 0

        self.wake_main = wake_main
        self.ser = None

        # erstelle hier die serielle Verbindung
        try:
            self.ser = self.init(self.port, self.baud)
        except serial.SerialException:
            self.connected = False
            return

    def init(self, port, baud):  # initialiesiert Serielles Objekt
        """Initialisiert Threads und die serielle Verbindung."""

        serial_conn = serial.Serial(port, baud)

        recv_thread = threading.Thread(target=self.listen,
                                       args=(self.killflag, serial_conn, self.recv_queue,), daemon=True)
        recv_thread.start()
        self.recv_thread = recv_thread

        send_thread = threading.Thread(target=self.print,
                                       args=(self.killflag, self.dataflag, serial_conn, self.send_queue,),
                                       daemon=True)
        send_thread.start()
        self.send_thread = send_thread

        self.connected = True

        self.send_thread_n = send_thread.native_id
        self.recv_thread_n = recv_thread.native_id

        return serial_conn

    def kill(self):  # schliesst die serielle Verbindung
        """Beendet die serielle Verbindung und die dazugehoerigen Threads."""

        if not self.connected:
            return

        self.dataflag.set()
        self.killflag.set()

        self.ser.cancel_read()

        self.recv_thread.join()
        self.send_thread.join()
        self.ser.close()

        self.killflag.clear()

        self.connected = False

        self.recv_thread_n = 0
        self.send_thread_n = 0

        return

    def print(self, stop_flag, data_flag, ser, q_send):  # sendet das eingegebene
        """Sendet seriell Daten."""
        while not stop_flag.is_set():
            data_flag.wait()
            try:
                data = q_send.get(block=True, timeout=1)
            except queue.Empty:
                data_flag.clear()
            else:
                ser.write(bytes(data, "utf-8"))

        return

    def listen(self, stop_flag, ser, q_recv):  # liesst das serielle objekt (trennzeichen \n)
        """Liest Daten aus der seriellen Verbindung aus."""

        erhalten = ""
        falsche_baudrate = False

        while True:

            data = ser.read()

            if stop_flag.is_set():
                break

            if data:
                try:
                    data = data.decode("utf-8")
                except ValueError:
                    falsche_baudrate = True
                    erhalten = erhalten + "?"
                    continue

                if data == '\n':
                    q_recv.put(erhalten + '\n')
                    self.wake_main.set()
                    erhalten = ""
                else:
                    erhalten = erhalten + data
            if ser.inWaiting() == 0 and falsche_baudrate:
                q_recv.put(erhalten + '(nicht dekodierbare Zeichen!)\n')
                self.wake_main.set()
                erhalten = ""
                falsche_baudrate = False

        return

    def change_baud(self, baud):
        """Erstellt eine neue serielle Verbindung, mit der angegebenen Baudrate"""
        if self.connected:
            self.kill()

        self.ser = self.init(self.port, baud)
        self.baud = baud

    def change_port(self, port):
        """Erstellt eine neue serielle Verbindung, mit der angegebenen Baudrate"""
        if self.connected:
            self.kill()

        self.ser = self.init(port, self.baud)
        self.port = port
