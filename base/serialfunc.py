import time
import serial
import threading


class SerialFunc:

    def serial_init(port, baud):  # initialiesiert Serielles Objekt
        """Initialisiert Threads und die serielle Verbindung."""

        global serial_recv_thread
        global serial_send_thread
        global verbunden
        global serial_recv_queue
        global serial_send_queue
        global serial_kill_flag
        global send_data_flag
        serial_conn = serial.Serial(port, baud)

        serial_recv_thread = threading.Thread(target=serial_listen,
                                              args=(serial_kill_flag, serial_conn, serial_recv_queue,), daemon=True)
        serial_recv_thread.start()

        serial_send_thread = threading.Thread(target=serial_print,
                                              args=(serial_kill_flag, send_data_flag, serial_conn, serial_send_queue,),
                                              daemon=True)
        serial_send_thread.start()

        verbunden = True

        return serial_conn


    def serial_kill(serial_conn):  # schliesst die serielle Verbindung
        """Beendet die serielle Verbindung und die dazugehoerigen Threads."""

        global verbunden
        global serial_kill_flag
        global send_data_flag

        global serial_recv_thread
        global serial_send_thread

        if not verbunden:
            return

        send_data_flag.set()
        serial_kill_flag.set()

        serial_recv_thread.join()
        serial_send_thread.join()
        serial_conn.close()

        serial_kill_flag.clear()

        verbunden = False

        return


    def serial_print(stop_flag, data_flag, ser, q_send):  # sendet das eingegebene
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


    def serial_listen(stop_flag, ser, q_recv):  # liesst das serielle objekt (trennzeichen \n)
        """Liest Daten aus der seriellen Verbindung aus."""

        erhalten = ""
        falsche_baudrate = False

        while not stop_flag.is_set():
            if ser.inWaiting() > 0:
                data = ser.read()
                if data:
                    try:
                        data = data.decode("utf-8")
                    except ValueError:
                        falsche_baudrate = True
                        erhalten = erhalten + "?"
                        continue

                    if data == '\n':
                        q_recv.put(erhalten + '\n')
                        erhalten = ""
                    else:
                        erhalten = erhalten + data
            if ser.inWaiting() == 0 and falsche_baudrate:
                q_recv.put(erhalten + '(nicht dekodierbare Zeichen!)\n')
                erhalten = ""
                falsche_baudrate = False

            time.sleep(0.001)
        return


