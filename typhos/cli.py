"""This module defines the ``typhos`` command line utility"""
import argparse
import logging
import sys
import re
import ast

import coloredlogs
from qtpy.QtWidgets import QApplication, QMainWindow

import pcdsutils
import typhos

logger = logging.getLogger(__name__)
app = None

# Argument Parser Setup
parser = argparse.ArgumentParser(description='Create a TyphosSuite for '
                                             'device/s stored in a Happi '
                                             'Database')

parser.add_argument('devices', nargs='*',
                    help='Device names to load in the TyphosSuite or '
                         'class name with parameters on the format: '
                         'package.ClassName[{"param1":"val1",...}]')
parser.add_argument('--happi-cfg',
                    help='Location of happi configuration file '
                         'if not specified by $HAPPI_CFG environment variable')
parser.add_argument('--version', '-V', action='store_true',
                    help='Current version and location '
                         'of Typhos installation.')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Show the debug logging stream')
parser.add_argument('--dark', action='store_true',
                    help='Use the QDarkStyleSheet shipped with Typhos')
parser.add_argument('--stylesheet',
                    help='Additional stylesheet options')


# Append to module docs
__doc__ += '\n::\n\n    ' + parser.format_help().replace('\n', '\n    ')


def typhos_cli_setup(args):
    global app
    # Logging Level handling
    logging.getLogger().addHandler(logging.NullHandler())
    shown_logger = logging.getLogger('typhos')
    if args.verbose:
        level = "DEBUG"
    else:
        level = "INFO"
    coloredlogs.install(level=level, logger=shown_logger,
                        fmt='[%(asctime)s] - %(levelname)s -  %(message)s')
    logger.debug("Set logging level of %r to %r", shown_logger.name, level)

    # Version endpoint
    if args.version:
        print(f'Typhos: Version {typhos.__version__} from {typhos.__file__}')
        return

    # Deal with stylesheet
    if not app:
        logger.debug("Creating QApplication ...")
        app = QApplication([])

    logger.debug("Applying stylesheet ...")
    typhos.use_stylesheet(dark=args.dark)
    if args.stylesheet:
        logger.info("Loading QSS file %r ...", args.stylesheet)
        with open(args.stylesheet, 'r') as handle:
            app.setStyleSheet(handle.read())


def create_suite(devices, cfg=None):
    """Create a TyphosSuite from a list of device names"""
    logger.debug("Accessing Happi Client ...")
    happi_enabled = False
    try:
        import happi
        import typhos.plugins.happi
        happi_enabled = True
    except (ImportError, ModuleNotFoundError):
        logger.exception("Unable to import happi to load devices!")

    if happi_enabled:
        if typhos.plugins.happi.HappiClientState.client:
            logger.debug("Using happi Client already registered with Typhos")
            client = typhos.plugins.happi.HappiClientState.client
        else:
            logger.debug("Creating new happi Client from configuration")
            client = happi.Client.from_config(cfg=cfg)

    # Load and add each device
    loaded_devs = list()

    klass_regex = re.compile(
        r'([a-zA-Z][a-zA-Z\.\_]*)\[(\{.+})*[\,]*\]'  # noqa
    )

    for device in devices:
        logger.info("Loading %r ...", device)
        result = klass_regex.findall(device)
        if len(result) > 0:
            try:
                klass, args = result[0]
                default_kwargs = {"name": "device"}
                if args:
                    kwargs = ast.literal_eval(args)
                    default_kwargs.update(kwargs)

                device = pcdsutils.utils.import_helper(klass)(**default_kwargs)
                loaded_devs.append(device)
            except Exception:
                logger.exception("Unable to load class entry: %s with args %s",
                                 klass, args)
        else:
            if not happi_enabled:
                logger.error("Happi not available. Unable to load entry: %r",
                             device)
                continue
            try:
                device = client.load_device(name=device)
                loaded_devs.append(device)
            except Exception:
                logger.exception("Unable to load Happi entry: %r", device)
    if loaded_devs or not devices:
        logger.debug("Creating empty TyphosSuite ...")
        suite = typhos.TyphosSuite()
        logger.info("Loading Tools ...")
        tools = dict(suite.default_tools)
        tools.pop("StripTool")
        for name, tool in tools.items():
            suite.add_tool(name, tool())
        if devices:
            logger.info("Adding devices ...")
        for device in loaded_devs:
            try:
                suite.add_device(device)
                suite.show_subdisplay(device)
            except Exception:
                logger.exception("Unable to add %r to TyphosSuite",
                                 device.name)
        return suite


def typhos_cli(args):
    """Command Line Application for Typhos"""
    args = parser.parse_args(args)
    typhos_cli_setup(args)
    if not args.version:
        with typhos.utils.no_device_lazy_load():
            suite = create_suite(args.devices, cfg=args.happi_cfg)
        if suite:
            window = QMainWindow()
            window.setCentralWidget(suite)
            window.show()
            logger.info("Launching application ...")
            QApplication.instance().exec_()
            logger.info("Execution complete!")
            return window


def main():
    """Execute the ``typhos_cli`` with command line arguments"""
    typhos_cli(sys.argv[1:])