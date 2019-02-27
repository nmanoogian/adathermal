import bbcode


class BBCodeTag:

    def __init__(self, name, description, on_open, on_close):
        self.name = name
        self.description = description
        self.on_open = on_open
        self.on_close = on_close


class BBCodeAdapter:
    tags = [
        BBCodeTag(
            name="m",
            description="Medium-sized text",
            on_open=lambda p: p.set_size("M"),
            on_close=lambda p: p.set_size("S"),
        ),
        BBCodeTag(
            name="l",
            description="Large-sized text",
            on_open=lambda p: p.set_size("L"),
            on_close=lambda p: p.set_size("S"),
        ),
        BBCodeTag(
            name="b",
            description="Bold text",
            on_open=lambda p: p.bold_on(),
            on_close=lambda p: p.bold_off(),
        ),
        BBCodeTag(
            name="s",
            description="Strike-through text",
            on_open=lambda p: p.strike_on(),
            on_close=lambda p: p.strike_off(),
        ),
    ]

    def __init__(self, printer):
        self.printer = printer

    def print(self, raw):
        parser = bbcode.Parser()
        for tag in BBCodeAdapter.tags:
            parser.add_simple_formatter(tag.name, "%(value)s")
        tokens = parser.tokenize(raw)
        for token in tokens:
            token_type, tag_name, _, token_text = token
            tag = next((t for t in BBCodeAdapter.tags if t.name == tag_name), None)
            if token_type == bbcode.Parser.TOKEN_DATA or tag is None:
                self.printer.print(token_text)
            elif token_type == bbcode.Parser.TOKEN_NEWLINE:
                self.printer.print("\n")
            else:
                if token_type == bbcode.Parser.TOKEN_TAG_START:
                    tag.on_open(self.printer)
                else:
                    tag.on_close(self.printer)
