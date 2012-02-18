from awwparse import Application, Command, options, arguments


class ACommand(Command):
    an_option = options.String(
        "-f", "--foo",
        action=lambda ns, n, s: ns.set(n, s)
    )
    an_argument = arguments.String()


class YourApp(Application):
    a_global_option = options.Integer("-i", "--integer")
    another_global_option = options.Boolean("-b", "--boolean")

    @ACommand.calling(with_name="spam")
    def foo(self, an_option=None, **kwargs):
        print "foo was here"
        print an_option
        print kwargs

    def run(self, **parameters):
        print "run was here"
        print parameters


if __name__ == "__main__":
    app = YourApp()
    app()
