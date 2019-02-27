import math
import sys
import time

from serial import Serial


class ThermalPrinter(Serial):
    resume_time = 0.0
    byte_time = 0.0
    dot_print_time = 0.0
    dot_feed_time = 0.0
    prev_byte = '\n'
    column = 0
    max_column = 32
    char_height = 24
    line_spacing = 8
    barcode_height = 50
    print_mode = 0
    default_heat_time = 120
    firmware_version = 268
    write_to_stdout = False

    def __init__(self, *args, **kwargs):
        # NEW BEHAVIOR: if no parameters given, output is written
        # to stdout, to be piped through 'lp -o raw' (old behavior
        # was to use default port & baud rate).
        baudrate = 19200
        if len(args) == 0:
            self.write_to_stdout = True
        if len(args) == 1:
            # If only port is passed, use default baud rate.
            args = [args[0], baudrate]
        elif len(args) == 2:
            # If both passed, use those values.
            baudrate = args[1]

        # Firmware is assumed version 2.68.  Can override this
        # with the 'firmware=X' argument, where X is the major
        # version number * 100 + the minor version number (e.g.
        # pass "firmware=264" for version 2.64.
        self.firmware_version = kwargs.get('firmware', 268)

        if self.write_to_stdout is False:
            # Calculate time to issue one byte to the printer.
            # 11 bits (not 8) to accommodate idle, start and
            # stop bits.  Idle time might be unnecessary, but
            # erring on side of caution here.
            self.byte_time = 11.0 / float(baudrate)

            Serial.__init__(self, *args, **kwargs)

            # Remainder of this method was previously in begin()

            # The printer can't start receiving data immediately
            # upon power up -- it needs a moment to cold boot
            # and initialize.  Allow at least 1/2 sec of uptime
            # before printer can receive data.
            self.timeout_set(0.5)

            self.wake()
            self.reset()

            # Description of print settings from p. 23 of manual:
            # ESC 7 n1 n2 n3 Setting Control Parameter Command
            # Decimal: 27 55 n1 n2 n3
            # max heating dots, heating time, heating interval
            # n1 = 0-255 Max heat dots, Unit (8dots), Default: 7 (64 dots)
            # n2 = 3-255 Heating time, Unit (10us), Default: 80 (800us)
            # n3 = 0-255 Heating interval, Unit (10us), Default: 2 (20us)
            # The more max heating dots, the more peak current
            # will cost when printing, the faster printing speed.
            # The max heating dots is 8*(n1+1).  The more heating
            # time, the more density, but the slower printing
            # speed.  If heating time is too short, blank page
            # may occur.  The more heating interval, the more
            # clear, but the slower printing speed.

            heat_time = kwargs.get('heattime', self.default_heat_time)
            self.write_bytes(
                27,  # Esc
                55,  # 7 (print settings)
                11,  # Heat dots
                heat_time,  # Lib default
                40)  # Heat interval

            # Description of print density from p. 23 of manual:
            # DC2 # n Set printing density
            # Decimal: 18 35 n
            # D4..D0 of n is used to set the printing density.
            # Density is 50% + 5% * n(D4-D0) printing density.
            # D7..D5 of n is used to set the printing break time.
            # Break time is n(D7-D5)*250us.
            # (Unsure of default values -- not documented)

            print_density = 10  # 100%
            print_break_time = 2  # 500 uS

            self.write_bytes(
                18,  # DC2
                35,  # Print density
                (print_break_time << 5) | print_density)
            self.dot_print_time = 0.03
            self.dot_feed_time = 0.0021
        else:
            self.reset()  # Inits some vars

    # Because there's no flow control between the printer and computer,
    # special care must be taken to avoid overrunning the printer's
    # buffer.  Serial output is throttled based on serial speed as well
    # as an estimate of the device's print and feed rates (relatively
    # slow, being bound to moving parts and physical reality).  After
    # an operation is issued to the printer (e.g. bitmap print), a
    # timeout is set before which any other printer operations will be
    # suspended.  This is generally more efficient than using a delay
    # in that it allows the calling code to continue with other duties
    # (e.g. receiving or decoding an image) while the printer
    # physically completes the task.

    # Sets estimated completion time for a just-issued task.
    def timeout_set(self, x):
        self.resume_time = time.time() + x

    # Waits (if necessary) for the prior task to complete.
    def timeout_wait(self):
        if self.write_to_stdout is False:
            while (time.time() - self.resume_time) < 0: pass

    # Printer performance may vary based on the power supply voltage,
    # thickness of paper, phase of the moon and other seemingly random
    # variables.  This method sets the times (in microseconds) for the
    # paper to advance one vertical 'dot' when printing and feeding.
    # For example, in the default initialized state, normal-sized text
    # is 24 dots tall and the line spacing is 32 dots, so the time for
    # one line to be issued is approximately 24 * print time + 8 * feed
    # time.  The default print and feed times are based on a random
    # test unit, but as stated above your reality may be influenced by
    # many factors.  This lets you tweak the timing to avoid excessive
    # delays and/or overrunning the printer buffer.
    def set_times(self, p, f):
        # Units are in microseconds for
        # compatibility with Arduino library
        self.dot_print_time = p / 1000000.0
        self.dot_feed_time = f / 1000000.0

    # 'Raw' byte-writing method
    def write_bytes(self, *args):
        if self.write_to_stdout:
            for arg in args:
                sys.stdout.write(str(arg))
        else:
            self.timeout_wait()
            self.timeout_set(len(args) * self.byte_time)
            for arg in args:
                super(ThermalPrinter, self).write(bytes([arg]))

    # Override write() method to keep track of paper feed.
    def write(self, data):
        for i in range(len(data)):
            c = data[i]
            if self.write_to_stdout:
                sys.stdout.write(str(c))
                continue
            if ord(c) != 0x13:
                self.timeout_wait()
                super(ThermalPrinter, self).write(c.encode('cp437', 'ignore'))
                d = self.byte_time
                if ((c == '\n') or
                        (self.column == self.max_column)):
                    # Newline or wrap
                    if self.prev_byte == '\n':
                        # Feed line (blank)
                        d += ((self.char_height +
                               self.line_spacing) *
                              self.dot_feed_time)
                    else:
                        # Text line
                        d += ((self.char_height *
                               self.dot_print_time) +
                              (self.line_spacing *
                               self.dot_feed_time))
                        self.column = 0
                        # Treat wrap as newline
                        # on next pass
                        c = '\n'
                else:
                    self.column += 1
                self.timeout_set(d)
                self.prev_byte = c

    # The bulk of this method was moved into __init__,
    # but this is left here for compatibility with older
    # code that might get ported directly from Arduino.
    def begin(self, heat_time=default_heat_time):
        self.write_bytes(
            27,  # Esc
            55,  # 7 (print settings)
            11,  # Heat dots
            heat_time,
            40)  # Heat interval

    def reset(self):
        self.write_bytes(27, 64)  # Esc @ = init command
        self.prev_byte = '\n'  # Treat as if prior line is blank
        self.column = 0
        self.max_column = 32
        self.char_height = 24
        self.line_spacing = 6
        self.barcode_height = 50
        if self.firmware_version >= 264:
            # Configure tab stops on recent printers
            self.write_bytes(27, 68)  # Set tab stops
            self.write_bytes(4, 8, 12, 16)  # every 4 columns,
            self.write_bytes(20, 24, 28, 0)  # 0 is end-of-list.

    # Reset text formatting parameters.
    def set_default(self):
        self.online()
        self.justify('L')
        self.inverse_off()
        self.double_height_off()
        self.set_line_height(30)
        self.bold_off()
        self.underline_off()
        self.set_barcode_height(50)
        self.set_size('s')
        self.set_charset()
        self.set_code_page()

    def test(self):
        self.write("Hello world!")
        self.feed(2)

    def test_page(self):
        self.write_bytes(18, 84)
        self.timeout_set(
            self.dot_print_time * 24 * 26 +
            self.dot_feed_time * (6 * 26 + 30))

    def set_barcode_height(self, val=50):
        if val < 1: val = 1
        self.barcode_height = val
        self.write_bytes(29, 104, val)

    UPC_A = 0
    UPC_E = 1
    EAN13 = 2
    EAN8 = 3
    CODE39 = 4
    I25 = 5
    CODEBAR = 6
    CODE93 = 7
    CODE128 = 8
    CODE11 = 9
    MSI = 10
    ITF = 11
    CODABAR = 12

    def print_barcode(self, text, type):

        new_dict = {  # UPC codes & values for firmwareVersion >= 264
            self.UPC_A: 65,
            self.UPC_E: 66,
            self.EAN13: 67,
            self.EAN8: 68,
            self.CODE39: 69,
            self.ITF: 70,
            self.CODABAR: 71,
            self.CODE93: 72,
            self.CODE128: 73,
            self.I25: -1,  # NOT IN NEW FIRMWARE
            self.CODEBAR: -1,
            self.CODE11: -1,
            self.MSI: -1
        }
        old_dict = {  # UPC codes & values for firmwareVersion < 264
            self.UPC_A: 0,
            self.UPC_E: 1,
            self.EAN13: 2,
            self.EAN8: 3,
            self.CODE39: 4,
            self.I25: 5,
            self.CODEBAR: 6,
            self.CODE93: 7,
            self.CODE128: 8,
            self.CODE11: 9,
            self.MSI: 10,
            self.ITF: -1,  # NOT IN OLD FIRMWARE
            self.CODABAR: -1
        }

        if self.firmware_version >= 264:
            n = new_dict[type]
        else:
            n = old_dict[type]
        if n == -1:
            return
        self.feed(1)  # Recent firmware requires this?
        self.write_bytes(
            29, 72, 2,  # Print label below barcode
            29, 119, 3,  # Barcode width
            29, 107, n)  # Barcode type
        self.timeout_wait()
        self.timeout_set((self.barcode_height + 40) * self.dot_print_time)
        # Print string
        if self.firmware_version >= 264:
            # Recent firmware: write length byte + string sans NUL
            n = len(text)
            if n > 255: n = 255
            if self.write_to_stdout:
                sys.stdout.write(str(n))
                for i in range(n):
                    sys.stdout.write(str(text[i]))
            else:
                super(ThermalPrinter, self).write(n)
                for i in range(n):
                    super(ThermalPrinter,
                          self).write(text[i])
        else:
            # Older firmware: write string + NUL
            if self.write_to_stdout:
                sys.stdout.write(str(text))
            else:
                super(ThermalPrinter, self).write(text.encode("utf-8", "ignore"))
        self.prev_byte = '\n'

    # === Character commands ===

    INVERSE_MASK = (1 << 1)  # Not in 2.6.8 firmware (see inverseOn())
    UPDOWN_MASK = (1 << 2)
    BOLD_MASK = (1 << 3)
    DOUBLE_HEIGHT_MASK = (1 << 4)
    DOUBLE_WIDTH_MASK = (1 << 5)
    STRIKE_MASK = (1 << 6)

    def set_print_mode(self, mask):
        self.print_mode |= mask
        self.write_print_mode()
        if self.print_mode & self.DOUBLE_HEIGHT_MASK:
            self.char_height = 48
        else:
            self.char_height = 24
        if self.print_mode & self.DOUBLE_WIDTH_MASK:
            self.max_column = 16
        else:
            self.max_column = 32

    def unset_print_mode(self, mask):
        self.print_mode &= ~mask
        self.write_print_mode()
        if self.print_mode & self.DOUBLE_HEIGHT_MASK:
            self.char_height = 48
        else:
            self.char_height = 24
        if self.print_mode & self.DOUBLE_WIDTH_MASK:
            self.max_column = 16
        else:
            self.max_column = 32

    def write_print_mode(self):
        self.write_bytes(27, 33, self.print_mode)

    def normal(self):
        self.print_mode = 0
        self.write_print_mode()

    def inverseOn(self):
        if self.firmware_version >= 268:
            self.write_bytes(29, 66, 1)
        else:
            self.set_print_mode(self.INVERSE_MASK)

    def inverse_off(self):
        if self.firmware_version >= 268:
            self.write_bytes(29, 66, 0)
        else:
            self.unset_print_mode(self.INVERSE_MASK)

    def upside_down_on(self):
        self.set_print_mode(self.UPDOWN_MASK)

    def upside_down_off(self):
        self.unset_print_mode(self.UPDOWN_MASK)

    def double_height_on(self):
        self.set_print_mode(self.DOUBLE_HEIGHT_MASK)

    def double_height_off(self):
        self.unset_print_mode(self.DOUBLE_HEIGHT_MASK)

    def double_width_on(self):
        self.set_print_mode(self.DOUBLE_WIDTH_MASK)

    def double_width_off(self):
        self.unset_print_mode(self.DOUBLE_WIDTH_MASK)

    def strike_on(self):
        self.set_print_mode(self.STRIKE_MASK)

    def strike_off(self):
        self.unset_print_mode(self.STRIKE_MASK)

    def bold_on(self):
        self.set_print_mode(self.BOLD_MASK)

    def bold_off(self):
        self.unset_print_mode(self.BOLD_MASK)

    def justify(self, value):
        c = value.upper()
        if c == 'C':
            pos = 1
        elif c == 'R':
            pos = 2
        else:
            pos = 0
        self.write_bytes(0x1B, 0x61, pos)

    # Feeds by the specified number of lines
    def feed(self, x=1):
        if self.firmware_version >= 264:
            self.write_bytes(27, 100, x)
            self.timeout_set(self.dot_feed_time * self.char_height)
            self.prev_byte = '\n'
            self.column = 0

        else:
            # datasheet claims sending bytes 27, 100, <x> works,
            # but it feeds much more than that.  So, manually:
            while x > 0:
                self.write('\n')
                x -= 1

    # Feeds by the specified number of individual pixel rows
    def feed_rows(self, rows):
        self.write_bytes(27, 74, rows)
        self.timeout_set(rows * self.dot_feed_time)
        self.prev_byte = '\n'
        self.column = 0

    def flush(self):
        self.write_bytes(12)  # ASCII FF

    def set_size(self, value):
        c = value.upper()
        if c == 'L':  # Large: double width and height
            size = 0x11
            self.char_height = 48
            self.max_column = 16
        elif c == 'M':  # Medium: double height
            size = 0x01
            self.char_height = 48
            self.max_column = 32
        else:  # Small: standard width and height
            size = 0x00
            self.char_height = 24
            self.max_column = 32

        self.write_bytes(29, 33, size)
        prevByte = '\n'  # Setting the size adds a linefeed

    # Underlines of different weights can be produced:
    # 0 - no underline
    # 1 - normal underline
    # 2 - thick underline
    def underline_on(self, weight=1):
        if weight > 2:
            weight = 2
        self.write_bytes(27, 45, weight)

    def underline_off(self):
        self.write_bytes(27, 45, 0)

    def print_bitmap(self, w, h, bitmap, laa_t=False):
        row_bytes = math.floor((w + 7) / 8)  # Round up to next byte boundary
        if row_bytes >= 48:
            row_bytes_clipped = 48  # 384 pixels max width
        else:
            row_bytes_clipped = row_bytes

        # if laa_t (line-at-a-time) is True, print bitmaps
        # scanline-at-a-time (rather than in chunks).
        # This tends to make for much cleaner printing
        # (no feed gaps) on large images...but has the
        # opposite effect on small images that would fit
        # in a single 'chunk', so use carefully!
        if laa_t:
            max_chunk_height = 1
        else:
            max_chunk_height = 255

        i = 0
        for rowStart in range(0, h, max_chunk_height):
            chunk_height = h - rowStart
            if chunk_height > max_chunk_height:
                chunk_height = max_chunk_height

            # Timeout wait happens here
            self.write_bytes(18, 42, chunk_height, row_bytes_clipped)

            for y in range(chunk_height):
                for x in range(row_bytes_clipped):
                    if self.write_to_stdout:
                        sys.stdout.write(str(bitmap[i]))
                    else:
                        super(ThermalPrinter,
                              self).write(bytes([bitmap[i]]))
                    i += 1
                i += row_bytes - row_bytes_clipped
            self.timeout_set(chunk_height * self.dot_print_time)

        self.prev_byte = '\n'

    # Print Image.  Requires Python Imaging Library.  This is
    # specific to the Python port and not present in the Arduino
    # library.  Image will be cropped to 384 pixels width if
    # necessary, and converted to 1-bit w/diffusion dithering.
    # For any other behavior (scale, B&W threshold, etc.), use
    # the Imaging Library to perform such operations before
    # passing the result to this function.
    def print_image(self, image, laa_t=False):
        if image.mode != '1':
            image = image.convert('1')

        width = image.size[0]
        height = image.size[1]
        if width > 384:
            width = 384
        row_bytes = (width + 7) / 8
        bitmap = bytearray(row_bytes * height)
        pixels = image.load()

        for y in range(height):
            n = y * row_bytes
            x = 0
            for b in range(row_bytes):
                sum = 0
                bit = 128
                while bit > 0:
                    if x >= width: break
                    if pixels[x, y] == 0:
                        sum |= bit
                    x += 1
                    bit >>= 1
                bitmap[n + b] = sum

        self.print_bitmap(width, height, bitmap, laa_t)

    # Take the printer offline. Print commands sent after this
    # will be ignored until 'online' is called.
    def offline(self):
        self.write_bytes(27, 61, 0)

    # Take the printer online. Subsequent print commands will be obeyed.
    def online(self):
        self.write_bytes(27, 61, 1)

    # Put the printer into a low-energy state immediately.
    def sleep(self):
        self.sleep_after(1)  # Can't be 0, that means "don't sleep"

    # Put the printer into a low-energy state after
    # the given number of seconds.
    def sleep_after(self, seconds):
        if self.firmware_version >= 264:
            self.write_bytes(27, 56, seconds & 0xFF, seconds >> 8)
        else:
            self.write_bytes(27, 56, seconds)

    def wake(self):
        self.timeout_set(0)
        self.write_bytes(255)
        if self.firmware_version >= 264:
            time.sleep(0.05)  # 50 ms
            self.write_bytes(27, 118, 0)  # Sleep off (important!)
        else:
            for i in range(10):
                self.write_bytes(27)
                self.timeout_set(0.1)

    # Check the status of the paper using the printers self reporting
    # ability. Doesn't match the datasheet...
    # Returns True for paper, False for no paper.
    def has_paper(self):
        if self.firmware_version >= 264:
            self.write_bytes(27, 118, 0)
        else:
            self.write_bytes(29, 114, 0)
        # Bit 2 of response seems to be paper status
        stat = ord(self.read(1)) & 0b00000100
        # If set, we have paper; if clear, no paper
        return stat == 0

    def set_line_height(self, val=32):
        if val < 24:
            val = 24
        self.line_spacing = val - 24

        # The printer doesn't take into account the current text
        # height when setting line height, making this more akin
        # to inter-line spacing.  Default line spacing is 32
        # (char height of 24, line spacing of 8).
        self.write_bytes(27, 51, val)

    CHARSET_USA = 0
    CHARSET_FRANCE = 1
    CHARSET_GERMANY = 2
    CHARSET_UK = 3
    CHARSET_DENMARK1 = 4
    CHARSET_SWEDEN = 5
    CHARSET_ITALY = 6
    CHARSET_SPAIN1 = 7
    CHARSET_JAPAN = 8
    CHARSET_NORWAY = 9
    CHARSET_DENMARK2 = 10
    CHARSET_SPAIN2 = 11
    CHARSET_LATINAMERICA = 12
    CHARSET_KOREA = 13
    CHARSET_SLOVENIA = 14
    CHARSET_CROATIA = 14
    CHARSET_CHINA = 15

    # Alters some chars in ASCII 0x23-0x7E range; see datasheet
    def set_charset(self, val=0):
        if val > 15:
            val = 15
        self.write_bytes(27, 82, val)

    CODEPAGE_CP437 = 0  # USA, Standard Europe
    CODEPAGE_KATAKANA = 1
    CODEPAGE_CP850 = 2  # Multilingual
    CODEPAGE_CP860 = 3  # Portuguese
    CODEPAGE_CP863 = 4  # Canadian-French
    CODEPAGE_CP865 = 5  # Nordic
    CODEPAGE_WCP1251 = 6  # Cyrillic
    CODEPAGE_CP866 = 7  # Cyrillic #2
    CODEPAGE_MIK = 8  # Cyrillic/Bulgarian
    CODEPAGE_CP755 = 9  # East Europe, Latvian 2
    CODEPAGE_IRAN = 10
    CODEPAGE_CP862 = 15  # Hebrew
    CODEPAGE_WCP1252 = 16  # Latin 1
    CODEPAGE_WCP1253 = 17  # Greek
    CODEPAGE_CP852 = 18  # Latin 2
    CODEPAGE_CP858 = 19  # Multilingual Latin 1 + Euro
    CODEPAGE_IRAN2 = 20
    CODEPAGE_LATVIAN = 21
    CODEPAGE_CP864 = 22  # Arabic
    CODEPAGE_ISO_8859_1 = 23  # West Europe
    CODEPAGE_CP737 = 24  # Greek
    CODEPAGE_WCP1257 = 25  # Baltic
    CODEPAGE_THAI = 26
    CODEPAGE_CP720 = 27  # Arabic
    CODEPAGE_CP855 = 28
    CODEPAGE_CP857 = 29  # Turkish
    CODEPAGE_WCP1250 = 30  # Central Europe
    CODEPAGE_CP775 = 31
    CODEPAGE_WCP1254 = 32  # Turkish
    CODEPAGE_WCP1255 = 33  # Hebrew
    CODEPAGE_WCP1256 = 34  # Arabic
    CODEPAGE_WCP1258 = 35  # Vietnam
    CODEPAGE_ISO_8859_2 = 36  # Latin 2
    CODEPAGE_ISO_8859_3 = 37  # Latin 3
    CODEPAGE_ISO_8859_4 = 38  # Baltic
    CODEPAGE_ISO_8859_5 = 39  # Cyrillic
    CODEPAGE_ISO_8859_6 = 40  # Arabic
    CODEPAGE_ISO_8859_7 = 41  # Greek
    CODEPAGE_ISO_8859_8 = 42  # Hebrew
    CODEPAGE_ISO_8859_9 = 43  # Turkish
    CODEPAGE_ISO_8859_15 = 44  # Latin 3
    CODEPAGE_THAI2 = 45
    CODEPAGE_CP856 = 46
    CODEPAGE_CP874 = 47

    # Selects alt symbols for 'upper' ASCII values 0x80-0xFF
    def set_code_page(self, val=0):
        if val > 47: val = 47
        self.write_bytes(27, 116, val)

    # Copied from Arduino lib for parity; may not work on all printers
    def tab(self):
        self.write_bytes(9)
        self.column = (self.column + 4) & 0xFC

    # Copied from Arduino lib for parity; may not work on all printers
    def set_char_spacing(self, spacing):
        self.write_bytes(27, 32, spacing)

    # Overloading print() in Python pre-3.0 is dirty pool,
    # but these are here to provide more direct compatibility
    # with existing code written for the Arduino library.
    def print(self, *args):
        for arg in args:
            self.write(str(arg))
