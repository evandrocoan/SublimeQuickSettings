#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import re
import sys

import pprint

import sublime
import sublime_plugin

def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.append( module )

# Import the debug tools
assert_path( os.path.join( os.path.dirname( os.path.dirname( os.path.realpath( __file__ ) ) ), 'PythonDebugTools' ) )

# Import the debugger
import debug_tools
import imp
imp.reload( debug_tools )
import debug_tools

import ast
import json

# Enable debug messages: (bitwise)
#
# 0   - Disabled debugging
# 1   - Error logging messages
# 2   - Settings loading notices
# 4   - Settings loading file contents
# 8   - Quick panel selection.
#
# 127 - All debugging levels at the same time.
log = debug_tools.Debugger( 9, "Debug", "DebugLog.txt" )

log.clear_log_file()
log( 1, "Debugging" )
log( 1, "..." )
log( 1, "..." )

default_preferences_file = 'Default|Preferences'

standard_settings_names = ( "Distraction Free", "Current Syntax", "Current Project", "This View" )
standard_settings_types = ('default', 'default_'+sublime.platform())


def show_quick_panel(view, options, done, highlighted=None):
    sublime.set_timeout(lambda: view.window().show_quick_panel(options, done, 0, -1, highlighted), 10)


def json_list(x):

    if not isinstance(d, list):
        raise ValueError("Expected a JSON list")

    d = sublime.decode_value(x)
    #sys.stderr.write("d: %s\n" % d)

    return d


def json_dict(x):

    if not isinstance(d, dict):
        raise ValueError("Expected a JSON dictionary")

    d = sublime.decode_value(x)
    #sys.stderr.write("d: %s\n" % d)

    return d


def show_input(view, caption, initial, on_done=None, on_change=None, on_cancel=None, on_load=None):
    window = view.window()

    def do_input():
        _initial = initial

        if not isinstance(_initial, str):
            _initial = sublime.encode_value(_initial)

        input_view = window.show_input_panel(caption, _initial, on_done=on_done, on_change=on_change, on_cancel=on_cancel)

        if on_load:
            on_load(input_view)

    sublime.set_timeout(do_input, 10)


def get_descriptions(data):
    r"""get descriptions from preferences string

    extract descriptions from passed ``data``.

    :param data:
        string containing json preferences file.

    This is only a rough parser and will fetch also keys from
    sub-dictionaries.  Calling function is responsible to
    select correct data.
    """
    COMMENT_RE = re.compile(r"(?s)\s*//\s?(.*)")
    COMMENT_RE2 = re.compile(r'''(?xs)
        (?:
            "(?:[^"\\]|\\.)*"
            | (?:(?!//)[^"])
        )+
        (//.*)
        ''')
    COMMENT_START = re.compile(r"^\s*/\*(.*)")
    COMMENT_END   = re.compile(r"(.*)\*/")
    KEY_RE     = re.compile(r'\s*"([^"]+)"\s*:')
    INDENT_RE = re.compile(r'^\s*')

    description = {}
    comment = ""
    is_comment = False

    for line in data.splitlines(1):

        if is_comment:
            m = COMMENT_END.search(line)

            if m:
                comment += m.group(1).rstrip()+"\n"
                is_comment = False

            else:
                comment += line

            continue

        m = COMMENT_START.match(line)

        if m:
            is_comment = True
            comment += m.group(1).rstrip()+"\n"
            continue

        m = COMMENT_RE.match(line)

        if m:
            s = m.group(1)

            if not s: s = "\n"
            comment += s
            continue

        m = COMMENT_RE2.match(line)

        if m:
            #sys.stderr.write("line1: %s\n" % (repr(line)))
            line = line[:m.start(1)].rstrip()+"\n"
            #sys.stderr.write("line2: %s\n" % (repr(line)))

        if not line.strip(): # empty line resets current comment
            comment = ""
            continue

        m = KEY_RE.match(line)

        if m:

            while comment.startswith('\n'):
                comment = comment[1:]

            indent = INDENT_RE.match(comment).group(0)

            if indent:
                comment = ''.join([ l.startswith(indent) and l[len(indent):] or l for l in comment.splitlines(1) ])
            description[m.group(1)] = {"description": comment.replace("\r", "") or "No help available :("}
            comment = ""

    return description


# resolution order of settings
#    Packages/Default/Preferences.sublime-settings
#    Packages/Default/Preferences (<platform>).sublime-settings
#    Packages/User/Preferences.sublime-settings
#    <Project Settings>
#    Packages/<syntax>/<syntax>.sublime-settings
#    Packages/User/<syntax>.sublime-settings
#    <Buffer Specific Settings>

def get_current_syntax(view, syntax=None):
    current_syntax = None
    settings = view.settings()

    if syntax:
        current_syntax = syntax

    elif settings.has('syntax'):
        current_syntax = settings.get('syntax')
        current_syntax = current_syntax.replace("Packages/", "").replace("/", "|").rsplit('.', 1)[0]

    return current_syntax


def save_preference(view, setting_name, key, value):
    log( 2, "save__preference" )
    log( 2, "save__preference, setting_name: " +  str( setting_name ) )
    log( 2, "save__preference, setting_name: " + str( key ) )
    log( 2, "save__preference, setting_name: " +  str( value ) )

    if setting_name == "This View":
        settings = view.settings()
        settings.set(key, value)
        return

    if setting_name == "Current Project":
        data = view.window().project_data()

        if 'settings' not in data:
            data['settings'] = {}

        data['settings'][key] = value
        view.window().set_project_data(data)
        return

    setting_name = os.path.basename(setting_name.replace("|", "/"))

    log( 2, "save__preference, setting_name: " + setting_name )
    settings = sublime.load_settings(setting_name+'.sublime-settings')

    settings.set(key, value)
    sublime.save_settings(setting_name+'.sublime-settings')


def load_preferences():
    log( 2, "load__preferences" )

    preferences = {}
    preferences_files = sublime.find_resources("*.sublime-settings")

    for preference_file in preferences_files:

        log( 2, "load__preferences, preference_file: {0}".format( preference_file ) )
        preference_name = preference_file.replace("Packages/", "").replace("/", "|").rsplit('.', 1)[0]

        log( 2, "load__preferences, preference_name: {0}".format( preference_name ) )
        platform = "any"

        if preference_name[-5:].lower() == "(osx)":
            preference_name = preference_name[:-6]
            platform = "osx"

        elif preference_name[-9:].lower() == "(windows)":
            preference_name = preference_name[:-10]
            platform = "windows"

        elif preference_name[-7:].lower() == "(linux)":
            preference_name = preference_name[:-8]
            platform = "linux"

        log( 2, "load__preferences, preference_name: {0}".format( preference_name ) )

        if "/User/" in preference_file:
            setting_type = "user"

        else:
            setting_type = "default"

        if platform != "any":
            setting_type = setting_type+"_"+platform

        if preference_name not in preferences:
            preferences[preference_name] = {}

        if setting_type not in preferences[preference_name]:
            preferences[preference_name][setting_type] = {}

        #sys.stderr.write("preference_name: %s, setting_type: %s\n" % (preference_name, setting_type))
        preference = preferences[preference_name][setting_type]

        log( 2, "preference: " + str( preference ) )
        preference_data = sublime.load_resource(preference_file)

        if preference_data:
            preference_settings = {}

            try:
                #import spdb ; spdb.start()
                description = get_descriptions(preference_data)

                #sys.stderr.write("preference_data: %s\n" % preference_)
                preference_data = sublime.decode_value(preference_data)

                for setting_name, setting_value in preference_data.items():

                    if setting_name not in description:
                        preference_settings[setting_name] = {"description": "No help available :("}

                    else:
                        preference_settings[setting_name] = description[setting_name]

                    preference_settings[setting_name]['value'] = setting_value

            except:
                log(1, "Error reading %s (preference_data is %s)", preference_file, preference_data)

            preference.update(preference_settings)

    # log( 2, "SHIT: " + preferences.encode('utf8') )

    # for shit in preferences:
    #     log( 2, "isinstance(" + str( shit ) + ", str):  " + str( isinstance(shit, str) ) )
    #     log( 2, "isinstance(" + str( shit ) + ", dict): " + str( isinstance(shit, dict) ) )
    #     log( 2, "shit: " + pprint.pformat( preferences[shit] ) )

    return preferences


# commands are
#
# Edit Preferences        --> User
# Edit Syntax Preferences --> User
#

class EditPreferencesCommand(sublime_plugin.WindowCommand):

    # meta.<setting_name>: {
    #      "widget": "select"
    #      "value": [ "", [caption, value] ]
    #      "validate": "Package Name.module.function"
    #      "tip": "text"      in status bar
    #      "help": "Packages/..." or "text"
    # }
    #

    def set_setting_value(self, setting_file, setting_name, value):

        if setting_file == "Current Syntax":
            setting_file = self.current_syntax

        save_preference(self.view, setting_file, setting_name, value)
        self.options_names[self.index][1] = sublime.encode_value(value, False)

        #settings = sublime.load_settings(setting_file+'.sublime-settings')
        #settings.set()

        #
        # settings = sublime.load_settings(preferences_filename())
        # ignored = settings.get('ignored_packages')
        # if not ignored:
        #     ignored = []
        # for package in packages:
        #     if not package in ignored:
        #         ignored.append(package)
        #         disabled.append(package)
        # settings.set('ignored_packages', ignored)
        # sublime.save_settings(preferences_filename())

    def make_pref_rec(self, setting_file, setting_type, setting_name, value):
        return "%s/%s/%s" % (setting_file, setting_type, setting_name), value

    def getUserValueAndDescription(self, setting_file, setting_name):
        """
            @setting_name   the name of the setting
            @setting_file   the name of the setting's file on self.setting_files[setting_file]

            @return key_path, key_value:

                    key_path:  Default/wrap_width (deprecated)
                    key_value: {'value': True, 'description': 'No help available :('}
        """
        platform = sublime.platform()
        settings = [ self.setting_files[setting_file], self.get_default_setting_names(setting_file) ]

        setting_types = \
        [
            "user_%s" % platform,
            "user",
            "default_%s" % platform,
            "default",
        ]

        for setting in settings:

            for setting_type in setting_types:

                if setting_type in setting:

                    if setting_name in setting[setting_type]:
                        return setting[setting_type][setting_name]

        return {'value': None, 'description': 'No help available :('}

    def get_default_setting_names(self, setting_name):
        pref_default = None

        if self.is_preferences(setting_name):
            pref_default = self.setting_files[default_preferences_file]

        else:
            pref_default = {'default': {}, 'default_'+sublime.platform(): {}}

        return pref_default

    def get_setting_names(self, setting_name):
        setting = self.setting_files[setting_name]
        # log( 2, "get__setting_names, setting:      " + str( setting ) )
        # log( 2, "get__setting_names, setting type: " + str( type( setting ) ) )

        if self.is_preferences(setting_name):
            pref_default = self.setting_files[default_preferences_file]

        else:
            pref_default = {'default': {}, 'default_'+sublime.platform(): {}}

        return set \
        (
            [ x
                for y in standard_settings_types
                for x in setting.get(y, {}).keys()
            ] +
            [ x
                for y in standard_settings_types
                for x in pref_default.get(y, {}).keys()
            ]
        )

    def is_preferences(self, setting_file):
        return setting_file in standard_settings_names

    def getDefaultValueAndDescription(self, setting_file, setting_name):
        """
        @setting_file  the name of the setting file name on self.setting_files
        @setting_name  the name of the setting

            setting_file: Preferences
            setting_name: word_wrap

            setting_file: Default
            setting_name: adaptive_dividers

        @return a dictionary with the keys `value` and `description` for the given setting file and setting name.

        {'value': 0, 'description': 'Set to a value other than 0 to force wrapping at that column rather than the\nwindow width\n'}
        {'value': './\\()"\'-:,.;<>~!@#$%^&*|+=[]{}`~?', 'description': 'Characters that are considered to separate words\n'}
        """
        setting = self.setting_files[setting_file]

        for item in 'default', 'default_'+sublime.platform():

            if setting_name in setting.get(item, {}):
                return setting[item][setting_name]

        if self.is_preferences(setting_file):
            return self.getDefaultValueAndDescription(default_preferences_file, setting_name)

        return None

    def getSettingMetadata(self, setting_file, setting_name, defaultValueAndDescription):
        """
            @setting_file                  the name of the setting file name on self.setting_files
            @setting_name                  the name of the setting
            @defaultValueAndDescription    a dictionary with the keys `value` and `description` for
                                            the given setting file and setting setting_file.
                                            {'value': 0, 'description': 'Set to a value other than 0 to force wrapping'}
            @return
        """
        meta = self.getDefaultValueAndDescription(setting_file, "meta."+setting_name)

        #sys.stderr.write("meta: %s\n" % meta)
        if meta:
            return meta.get('value')

        setting_value = defaultValueAndDescription.get('value')

        if isinstance(setting_value, bool):
            return \
            {
                'widget': 'select_bool'
            }

        if isinstance(setting_value, float):
            return \
            {
                'widget':   'input',
                'validate': 'float',
            }

        if isinstance(setting_value, int):
            return \
            {
                'widget':   'input',
                'validate': 'int',
            }

        if isinstance(setting_value, list):
            return \
            {
                'widget':   'input',
                'validate': 'json_list'
            }

        if isinstance(setting_value, dict):
            return \
            {
                'widget':   'input',
                'validate': 'json_dict'
            }

        return \
        {
            'widget': 'input'
        }

    def run_widget(self, option):
        log( 2, "run__widget, option: " + str( option ) )

        setting_file = option[0]
        setting_name = option[1]

        log( 2, "run__widget, setting_file: " + str( setting_file ) )
        log( 2, "run__widget, setting_name: " + str( setting_name ) )

        defaultValueAndDescription = self.getDefaultValueAndDescription(setting_file, setting_name)
        log( 2, "run__widget, defaultValueAndDescription: " + str( settingMetadata ) )

        settingMetadata = self.getSettingMetadata(setting_file, setting_name, defaultValueAndDescription)
        log( 2, "run__widget, settingMetadata: " + str( settingMetadata ) )

        userValueAndDescription = self.getUserValueAndDescription(setting_file, setting_name)
        log( 2, "run__widget, userValueAndDescription: " + str( settingMetadata ) )

        widget   = settingMetadata.get('widget', 'input')
        validate = settingMetadata.get('validate', 'str')
        args     = settingMetadata.get('args', {})

        log( 2, "run__widget, widget:   " + str( widget ) )
        log( 2, "run__widget, validate: " + str( validate ) )
        log( 2, "run__widget, args:     " + str( args ) )

        if isinstance(validate, list):
            validate_in_list = validate

            def _validate_element(x):

                if x in validate_in_list:
                    return x

                else:
                    raise ValueError("Value must be one of %s" % validate_in_list)

            validate = _validate_element

        elif '.' not in validate:
            validate = eval(validate)

        if hasattr(self, "widget_"+widget):
            widget_func = getattr(self, "widget_"+widget)

        widget_func(self, key_path, value=userValueAndDescription.get('value'),
                    default=defaultValueAndDescription.get('value'), validate=validate, **args)

    def change_value(self, options, index):
        setting_file = options[index][0]
        setting_name = options[index][1]

        log( 2, "change__value, setting_file: " + str( setting_file ) )
        log( 2, "change__value, setting_name:  " + str( setting_name ) )

        options = \
        [
            [ "Change Value", "" ],
        ]

    #       options = [
    #           [ "Set for anything", ""]
    #           [ "Set for syntax %s only" % syntax, "" ],
    #           [ "Set for this platform only", sublime.platform() ],
    #           [ "Set for OSX only", "" ],
    #           [ "Set for Windows only", "" ],
    #           [ "Set for Linux only", ""]
    #       ]

        spec = self.getDefaultValueAndDescription(setting_file, setting_name)
        view = self.window.active_view()

        def done(index):

            if index == 0:  # change value
                self.run_widget(options[index])

            if index == len(options)-1: # reset to default
                self.set_setting_value(options[index], spec.get('value'), spec.get('value'))

        if len(options) == 1:
            self.run_widget(options[index])

        else:
            show_quick_panel(self.window.active_view(), options, done)

    def shutdown(self):
        self.window.run_command("hide_panel", {"panel": "output.preferences_editor_help"})

    def run(self, setting_file=None, syntax_name=None):
        r"""
        :param syntax_name:
            Name of syntax, you want to edit settings for

        :param setting_file:
            Name of settings' file, you want to edit.
        """

        self.view          = self.window.active_view()
        self.setting_files = load_preferences()

        self.setting_file   = setting_file
        self.current_syntax = get_current_syntax(self.view, syntax_name)

        self.setting_files['This View'] = { 'default': {}, 'default_'+sublime.platform(): {} }
        self.setting_files['Current Project'] = { 'default': {}, 'default_'+sublime.platform(): {} }

        options_names = []
        options_paths = []
        options_desciptions = []

        options_names.insert( 0, [ "QUIT (Esc)", "End Edit Settings" ] )
        options_desciptions.insert( 0, { "description": "You can press Esc, or select this option to end editing settings.\n" } )

        if setting_file is None:
            # log( 2, "run, self.setting_files.keys(): " + json.dumps( self.setting_files.keys(), indent=4 ) )
            self.is_main_panel = True

            # options_names = \
            # [
            #     ["Preferences", "General Settings"],
            #     ["Distraction Free", "Preferences for Distraction Free Mode"],
            #     ["Current Syntax", "%s-specific Preferences" % self.current_syntax],
            #     ["Current Project", "Project-specific Preferences"],
            #     ["This View", "Preferences for this View only"]
            # ]

            # for setting_file in sorted(self.setting_files.keys()):
            for setting_file in self.setting_files.keys():
                log( 2, 'run, setting_file: ' + str( setting_file ) )
                options_names.append( [ setting_file, "Package Settings" ] )

        else:
            self.is_main_panel = False
            log( 2, 'run, setting_file: ' + str( setting_file ) )

            options_names.insert( 1, [ "BACK (Open the Main Menu)", "Choose another Setting to Edit" ] )
            options_desciptions.insert( 1, { "description": "Select this option to take another setting to edit.\n" } )

            # for setting_name in sorted(self.get_setting_names(setting_file)):
            for setting_name in self.get_setting_names(setting_file):
                log( 2, 'run, setting_name: ' + str( setting_name ) )

                option_path = [setting_file, setting_name]
                log( 2, 'run, option_path: ' + str( option_path ) )

                options_paths.append( option_path )
                userValueAndDescription = self.getUserValueAndDescription(setting_file, setting_name)

                log( 4, 'run, userValueAndDescription: ', json.dumps( userValueAndDescription, indent=4 ) )
                option_name = setting_file + '/' + setting_name

                log( 2, 'run, option_name: ' + str( option_name ) )
                options_names.append( [ option_name, sublime.encode_value( userValueAndDescription.get('value'), False ) ] )

                defaultValueAndDescription = self.getDefaultValueAndDescription(setting_file, setting_name)
                log( 4, "run, defaultValueAndDescription: ", json.dumps( defaultValueAndDescription, indent=4 ) )

                options_desciptions.append( defaultValueAndDescription )

        help_view = self.window.create_output_panel("preferences_editor_help")
        help_view.settings().set('auto_indent', False)

        self.window.run_command("show_panel", {"panel": "output.preferences_editor_help"})

        def on_highlighted(index):
            help_view.run_command("select_all")

            if index < len( options_desciptions ):
                help_view.run_command("insert", {"characters": options_desciptions[index]['description']})

            else:
                help_view.run_command("insert", {"characters": "Package Settings"})

            help_view.show(0)

        def done(index):
            log( 8, "run, done, index:              " + str( index ) )
            log( 8, "run, done, self.is_main_panel: " + str( self.is_main_panel ) )

            if index < 0:
                return self.shutdown()

            elif index == 0:
                self.shutdown()

            elif index == 1 and not self.is_main_panel:
                self.shutdown()
                self.window.run_command("edit_preferences")

            # When it is the main panel, the indexes are not shifted by 1
            elif self.is_main_panel:
                self.window.run_command("edit_preferences", {"setting_file": options_names[index][0]})

            # When it is not the main panel, the indexes are shifted by 1
            else:
                self.index = index
                self.change_value(options_names, index)

        log( 4, "run, options_names: " + json.dumps( options_names, indent=4 ) )

        self.options_names = options_names
        self.preferences_selector = lambda: show_quick_panel(self.view, self.options_names, done, on_highlighted)
        self.preferences_selector()



