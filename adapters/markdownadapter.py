import re


class MarkdownAdapter:

    def __init__(self, printer):
        self.printer = printer

    def print(self, raw):
        for line in raw.splitlines():
            header_match = re.match(r"(?P<hashes>#{1,2})\s*(?P<text>.*)", line)
            bold_match = re.match(r"\*(?P<text>.*)\*$", line)
            if header_match is not None:
                if len(header_match.group("hashes")) == 1:
                    self.printer.set_size("L")
                else:
                    self.printer.set_size("M")
                self.printer.print(header_match.group("text").encode("ascii", "ignore"))
                self.printer.set_size("S")
            elif bold_match is not None:
                self.printer.bold_on()
                self.printer.print(bold_match.group("text").encode("ascii", "ignore"))
                self.printer.bold_off()
            else:
                self.printer.print(line.encode("ascii", "ignore"))
