#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import re
import sys

import pprint

import sublime
import sublime_plugin


import ast
import json

# # Import the debugger
# from debug_tools import getLogger

# # Enable debug messages: (bitwise)
# #
# # 0   - Disabled debugging
# # 1   - Error logging messages
# # 2   - Settings loading notices
# # 4   - Settings loading file contents
# # 8   - Quick panel selection.
# #
# # 127 - All debugging levels at the same time.
# log = getLogger( 127, __name__ )

# #log.setup( "DebugLog.txt" )
# #log.clear()

# log( 2, "Debugging" )
# log( 2, "..." )
# log( 2, "..." )

this_view_file = 'Current/This View'
current_syntax_file = 'Current Syntax'
current_project_file = 'Current Project'
distraction_free_file = 'Distraction Free'
default_preferences_file = 'Preferences'

# This must be the snake case name of the main class
command_name = "quick_settings_edit_preferences"

standard_settings_types = ('default', 'default_'+sublime.platform(), 'user')
standard_settings_names = ( distraction_free_file, current_syntax_file, current_project_file, this_view_file )

last_access = {}
main_function_key = 'main_function'


def show_quick_panel(view, options, done, highlighted=None, last=-1):
    """
        Allow to add a default text to the quick panel API self.window.show_quick_panel
        https://github.com/SublimeTextIssues/Core/issues/1896
    """

    # How can I test whether a variable holds a lambda?
    # https://stackoverflow.com/questions/3655842/how-can-i-test-whether-a-variable-holds-a-lambda
    if callable( last ):
        last = last()

    sublime.set_timeout(lambda: view.window().show_quick_panel(options, done, sublime.KEEP_OPEN_ON_FOCUS_LOST, last, highlighted), 10)


def get_preference_name(file):
    return os.path.basename(file).rsplit('.', 1)[0]


def json_list(x):

    d = sublime.decode_value(x)
    #sys.stderr.write("d: %s\n" % d)

    if not isinstance(d, list):
        raise ValueError("Expected a JSON list")

    return d


def json_dict(x):

    d = sublime.decode_value(x)
    #sys.stderr.write("d: %s\n" % d)

    if not isinstance(d, dict):
        raise ValueError("Expected a JSON dictionary")

    return d


def show_input(view, caption, initial, on_done=None, on_change=None, on_cancel=None, on_load=None):
    window = view.window()

    def do_input():
        _initial = initial

        if not isinstance(_initial, str):
            _initial = json.dumps(_initial)

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
            description[m.group(1)] = {"description": comment.replace("\r", "") or "No help available"}
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
        current_syntax = get_preference_name(settings.get('syntax'))

    return current_syntax


def save_preference(view, setting_file, setting_name, value):
    # log( 2, "save__preference" )
    # log( 2, "save__preference, setting_file: " +  str( setting_file ) )
    # log( 2, "save__preference, setting_name: " + str( setting_name ) )
    # log( 2, "save__preference, value:        " +  str( value ) )

    if setting_file == this_view_file:
        settings = view.settings()
        settings.set(setting_name, value)
        return

    if setting_file == current_project_file:
        data = view.window().project_data()

        if 'settings' not in data:
            data['settings'] = {}

        data['settings'][setting_name] = value
        view.window().set_project_data(data)
        return

    setting_file = os.path.basename(setting_file)

    # log( 2, "save__preference, setting_file: " + setting_file )
    settings = sublime.load_settings(setting_file+'.sublime-settings')

    settings.set(setting_name, value)
    sublime.save_settings(setting_file+'.sublime-settings')


def load_preferences():
    # log( 2, "load__preferences" )

    preferences = {}
    preferences_files = sublime.find_resources("*.sublime-settings")

    for preference_file in preferences_files:

        # log( 2, "load__preferences, preference_file: {0}".format( preference_file ) )
        preference_name = get_preference_name(preference_file)

        # log( 2, "load__preferences, preference_name: {0}".format( preference_name ) )
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

        # log( 2, "load__preferences, preference_name: {0}".format( preference_name ) )

        if preference_name == "Base File":
            preference_name = default_preferences_file

        if preference_name == "Global":
            preference_name = default_preferences_file

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

        # log( 2, "preference: " + str( preference ) )
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
                        preference_settings[setting_name] = {"description": "No help available"}

                    else:
                        preference_settings[setting_name] = description[setting_name]

                    preference_settings[setting_name]['value'] = setting_value

            except:
                print( "load_preferences: Error reading %s (preference_data is %s)" % (preference_file, preference_data) )

            preference.update(preference_settings)

    # for item in preferences:
    #     print( "isinstance(" + str( item ) + ", str):  " + str( isinstance(item, str) ) )
    #     print( "isinstance(" + str( item ) + ", dict): " + str( isinstance(item, dict) ) )
    #     print( "item: " + json.dumps( preferences[item] ) )

    return preferences


def load_syntax_names():
    syntax_names = []
    syntax_types = [ "*.tmLanguage", "*.sublime-syntax" ]

    for syntax_type in syntax_types:
        syntaxes = sublime.find_resources(syntax_type)

        for syntax in syntaxes:
            syntax_names.append(os.path.basename(syntax).rsplit('.', 1)[0])

    return syntax_names


class HelperView():

    def __init__(self, window, help_view_name, is_enabled=True):
        self.window     = window
        self.is_enabled = is_enabled

        self.help_view      = self.window.create_output_panel(help_view_name)
        self.help_view_name = help_view_name

        self.help_view.settings().set('auto_indent', False)

    def disable_panel():
        self.is_enabled = False

    def enable_panel():
        self.is_enabled = True

    def run_command(self, command, args={}):

        if self.is_enabled:
            self.help_view.run_command(command, args)

    def show_panel(self):

        if self.is_enabled:
            self.window.run_command("show_panel", {"panel": "output."+self.help_view_name})

    def hide_panel(self):

        if self.is_enabled:
            self.window.run_command("hide_panel", {"panel": "output."+self.help_view_name})

    def focus_begining(self):

        if self.is_enabled:
            self.help_view.show(0)


# commands are
#
# Edit Preferences        --> User
# Edit Syntax Preferences --> User
#

class QuickSettingsEditPreferencesCommand(sublime_plugin.WindowCommand):

    # meta.<setting_name>: {
    #      "widget": "select"
    #      "value": [ "", [caption, value] ]
    #      "validate": "Package Name.module.function"
    #      "tip": "text"      in status bar
    #      "help": "Packages/..." or "text"
    # }
    #

    def set_setting_value(self, setting_file, setting_name, value):
        # log( 2, "set__setting_value, setting_file:      " + str( setting_file ) )
        # log( 2, "set__setting_value, setting_name:      " + str( setting_name ) )
        # log( 2, "set__setting_value, json.dumps(value): " + json.dumps(value) )

        if setting_file == current_syntax_file:
            setting_file = self.current_syntax

        save_preference(self.view, setting_file, setting_name, value)
        self.options_names[self.index][1] = json.dumps(value)

    def make_pref_rec(self, setting_file, setting_type, setting_name, value):
        return "%s/%s/%s" % (setting_file, setting_type, setting_name), value

    def getUserValueAndDescription(self, setting_file, setting_name):
        """
            @setting_name   the name of the setting
            @setting_file   the name of the setting's file on self.setting_files[setting_file]

            @return dictionary with the setting value and description
                    dict: {'value': True, 'description': 'No help available'}
        """
        _setting = {'value': None, 'description': 'No help available'}
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
                        _setting = setting[setting_type][setting_name]

                        if setting_file == this_view_file:
                            _setting['value'] = self.view.settings().get(setting_name)

                        elif setting_file == current_project_file:
                            data = self.view.window().project_data()

                            if 'settings' in data and setting_name in data['settings']:
                                _setting['value'] = data['settings'].get(setting_name)

                        return _setting

        return _setting

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
        return setting_file in self.syntax_names or setting_file in standard_settings_names

    def getDefaultValueAndDescription(self, setting_file, setting_name, is_metadata=False):
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

        for item in standard_settings_types:

            if setting_name in setting.get(item, {}):
                return setting[item][setting_name]

        if self.is_preferences(setting_file):
            return self.getDefaultValueAndDescription(default_preferences_file, setting_name, is_metadata)

        if is_metadata:
            return None

        return {'value': 0, 'description': 'No Description available'}

    def getSettingMetadata(self, setting_file, setting_name, defaultValueAndDescription):
        """
            @setting_file                  the name of the setting file name on self.setting_files
            @setting_name                  the name of the setting
            @defaultValueAndDescription    a dictionary with the keys `value` and `description` for
                                            the given setting file and setting setting_file.
                                            {'value': 0, 'description': 'Set to a value other than 0 to force wrapping'}
            @return
        """
        settingMetadata = self.getDefaultValueAndDescription(setting_file, "meta."+setting_name, True)
        # log( 8, "get_SettingMetadata, settingMetadata: " + str( settingMetadata ) )

        #sys.stderr.write("settingMetadata: %s\n" % settingMetadata)
        if settingMetadata:
            return settingMetadata.get('value')

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

    def widget_select_bool(self, option, value=None, validate=None):
        # log( 8, "widget__select_bool, option: %s" % str(option) )

        view    = self.window.active_view()
        options = ["BACK (Open the Last Menu)", "true", "false"]

        setting_file = option[0]
        setting_name = option[1]

        settings = view.settings()
        default  = settings.get(setting_name, "")

        def done(index):
            # log( 8, "widget__select_bool, done, index: " + str( index ) )
            view.erase_status("preferences_editor")

            if index < 1:
                settings.set( setting_name, default )

                if index < 0:
                    return self.shutdown()

            elif index == 1:
                self.set_setting_value(setting_file, setting_name, True)
                sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, 'True'))

            else:
                self.set_setting_value(setting_file, setting_name, False)
                sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, 'False'))

            self.preferences_selector()

        def highlight(index):

            if index < 1:
                settings.set(setting_name, default)

            elif index == 1:
                settings.set(setting_name, True)

            elif index == 2:
                settings.set(setting_name, False)

        # for op in options: log( 2, "op: {0}".format( op ) )
        view.set_status("preferences_editor", "Set %s" % (setting_file + '/' + setting_name))
        show_quick_panel(view, options, done, highlight)

    def widget_select(self, option, value=None, validate=None, values=[]):
        # log( 8, "widget__select, option: %s" % str(option) )
        view = self.window.active_view()

        setting_file = option[0]
        setting_name = option[1]

        settings = view.settings()
        default  = settings.get(setting_name, "")

        # values.append({})
        options  = []
        commands = []
        args     = []
        types    = []
        _values  = []

        if len( values ) > 0 and isinstance(values[0], dict):
            values.insert( 0, {"value": default, "caption": "Cancel Changes"} )

            for data in values:
                args.append( data.get('args', {}) )
                types.append( data.get('type', 'window') )
                _values.append( data.get('value') )
                options.append( data['caption'] )
                commands.append( data.get('command') )

        else:
            values.insert( 0, default )
            _values = values
            options = [ str(x) for x in values ]

        options.remove( default )
        options.insert( 0, [ "Cancel Changes" ] )

        def done(index):
            # log( 8, "widget__select, done, index: %s" % str(index) )
            view.erase_status("preferences_editor")

            if index < 1:
                settings.set( setting_name, default )

                if index == 0:
                    return self.preferences_selector()

                else:
                    return self.shutdown()

            # if command is set, let the command handle this preference
            if commands:

                if commands[index]:
                    context = view

                    if types[index] == "window":
                        context = view.window()

                    sublime.set_timeout(lambda: context.run_command(commands[index], args[index]), 10)
                    return

            self.set_setting_value(setting_file, setting_name, _values[index])
            sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, str(_values[index])))
            self.preferences_selector()

        def highlight(index):
            # log( 8, "widget__select, highlight: setting %s to %s" % (setting_name, _values[index]) )
            settings.set(setting_name, _values[index])

        view.set_status("preferences_editor", "Set %s" % (setting_file + '/' + setting_name))
        show_quick_panel(view, options, done, highlight)

    def widget_multiselect(self, option, value=None, validate=None, values=None):
        # log( 8, "widget__multiselect, option: %s" % str(option) )
        view = self.window.active_view()

        setting_file = option[0]
        setting_name = option[1]

        settings = view.settings()
        default  = settings.get(setting_name, "")

        if len( values ) > 0 and isinstance( values[0], str ):
            _values = [ dict(caption=_value, value=_value) for _value in values ]

        other = []

        def do_add_option():
            options = \
            [
                _value.get('caption', str(_value.get('value')))
                for _value in _values if _value['value'] not in value
            ]

            def done(index):

                if index < 0:
                    settings.set( setting_name, default )
                    return self.shutdown()

                value.append(other[index])
                settings.set(setting_name, value)
                do_show_panel()

            show_quick_panel(view, options, done)

        def do_remove_option():
            options = \
            [
                _value.get('caption', str(_value.get('value')))
                for _value in _values if _value['value'] in value
            ]

            def done(index):

                if index < 0:
                    settings.set( setting_name, default )
                    return self.shutdown()

                value.remove(value[index])
                settings.set(setting_name, value)
                do_show_panel()

            show_quick_panel(view, options, done)

        def do_show_panel():
            other[:] = [ _value['value'] for _value in _values if _value['value'] not in value ]

            options = \
            [
                ["Save Changes", json.dumps(value)],
                ["Add Option", "From: "+json.dumps(other)],
                ["Remove Option", "From:"+json.dumps(value)]
            ]

            def done(index):
                view.erase_status("preferences_editor")

                if index < 0:
                    settings.set( setting_name, default )
                    return self.shutdown()

                if index == 0:
                    self.set_setting_value(setting_file, setting_name, value)
                    sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, str( value )))
                    self.preferences_selector()

                if index == 1:

                    if len( other ) > 0:
                        do_add_option()

                    else:
                        sublime.status_message("No options available to add.")
                        do_show_panel()

                if index == 2:

                    if len( value ) > 0:
                        do_remove_option()

                    else:
                        sublime.status_message("No options available to remove.")
                        do_show_panel()

            view.set_status("preferences_editor", "Set %s" % (setting_file + '/' + setting_name))
            show_quick_panel(view, options, done)

        do_show_panel()

    def widget_select_resource(self, option, value=None, validate=None, find_resources=""):
        # log( 8, "widget__select_resource, option: %s" % str(option) )
        resources = sorted(sublime.find_resources(find_resources))

        setting_file = option[0]
        setting_name = option[1]

        view     = self.window.active_view()
        settings = self.view.settings()

        options = []
        default = settings.get(setting_name, "")

        for resource in resources:
            options.append( [ os.path.basename(resource), os.path.dirname(resource).replace("Packages/", "") ] )

        options.insert( 0, ["Cancel Selection", "Go back to the settings menu"] )
        resources.insert( 0, default )

        def done(index):
            view.erase_status("preferences_editor")

            if index < 1:
                settings.set( setting_name, default )

                if index == 0:
                    self.preferences_selector()

                else:
                    return self.shutdown()

            self.set_setting_value(setting_file, setting_name, resources[index])
            sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, str( resources[index] )))
            self.preferences_selector()

        def highlight(index):
            # log( 8, "widget__select_resource, highlight: setting %s to %s" % (setting_file, resources[index]) )
            settings.set(setting_name, resources[index])

        view.set_status("preferences_editor", "Set %s" % (setting_file + '/' + setting_name))
        show_quick_panel(view, options, done, highlight)

    def widget_input(self, option, value=None, validate=None):
        setting_file = option[0]
        setting_name = option[1]

        view = self.view
        view.set_status("preferences_editor", "Set %s" % (setting_file  + '/' + setting_name))

        settings = view.settings()
        default  = settings.get(setting_name, "")

        def done(value):
            view.erase_status("preferences_editor")

            try:
                value = validate(value)
                self.set_setting_value(setting_file, setting_name, value)
                sublime.status_message("Set %s to %s" % (setting_file + '/' + setting_name, str( value )))

            except ValueError as e:
                settings.set( setting_name, default )
                sublime.error_message("Invalid Value: %s" % e)

            self.preferences_selector()

        def change(value):

            try:
                value = validate(value)
                settings.set(setting_name, value)
                # log( 8, "widget__input, change: set %s to %s" % (setting_name, value) )

            except ValueError as e:
                settings.set( setting_name, default )
                sublime.status_message("Invalid Value: %s" % e)

        def cancel():
            settings.set( setting_name, default )
            view.erase_status("preferences_editor")
            self.preferences_selector()

        view.set_status("preferences_editor", "Set %s" % (setting_file + '/' + setting_name))
        show_input(self.view, setting_name, value, done, change, cancel)

    def run_widget(self, option):
        # log( 8, "run__widget, option: " + str( option ) )

        setting_file = option[0]
        setting_name = option[1]

        # log( 8, "run__widget, setting_file: " + str( setting_file ) )
        # log( 8, "run__widget, setting_name: " + str( setting_name ) )

        defaultValueAndDescription = self.getDefaultValueAndDescription(setting_file, setting_name)
        # log( 8, "run__widget, defaultValueAndDescription: " + str( defaultValueAndDescription ) )

        settingMetadata = self.getSettingMetadata(setting_file, setting_name, defaultValueAndDescription)
        # log( 8, "run__widget, settingMetadata: " + str( settingMetadata ) )

        widget   = settingMetadata.get('widget', 'input')
        validate = settingMetadata.get('validate', 'str')
        args     = settingMetadata.get('args', {})

        # log( 8, "run__widget, widget:   " + str( widget ) )
        # log( 8, "run__widget, validate: " + str( validate ) )
        # log( 8, "run__widget, args:     " + str( args ) )

        userValueAndDescription = self.getUserValueAndDescription(setting_file, setting_name)
        # log( 8, "run__widget, userValueAndDescription: " + str( userValueAndDescription ) )

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

        widget_func(option, value=userValueAndDescription.get('value'), validate=validate, **args)

    def change_value(self, options_path, index):
        setting_file = options_path[index][0]
        setting_name = options_path[index][1]

        # log( 8, "change__value, setting_file: " + str( setting_file ) )
        # log( 8, "change__value, setting_name: " + str( setting_name ) )

        defaultValueAndDescription = self.getDefaultValueAndDescription(setting_file, setting_name)
        # log( 8, "change__value, defaultValueAndDescription: " + str( defaultValueAndDescription ) )

        self.run_widget(options_path[index])

    def shutdown(self):
        self.help_view.hide_panel()

    def run(self, setting_file=None, syntax_name=None):
        r"""
        :param syntax_name:
            Name of syntax, you want to edit settings for

        :param setting_file:
            Name of settings' file, you want to edit.
        """

        self.view          = self.window.active_view()
        self.setting_files = load_preferences()

        self.syntax_names   = load_syntax_names()
        self.setting_file   = setting_file
        self.current_syntax = get_current_syntax(self.view, syntax_name)

        for syntax in self.syntax_names:

            if syntax not in self.setting_files:
                self.setting_files[syntax] = { 'default': {}, 'default_'+sublime.platform(): {} }

        # https://bitbucket.org/klorenz/sublimepreferenceseditor/pull-requests/4
        if self.current_syntax in self.setting_files:
            self.setting_files[current_syntax_file] = self.setting_files[self.current_syntax]

        self.setting_files[this_view_file] = { 'default': {}, 'default_'+sublime.platform(): {} }
        self.setting_files[current_project_file] = { 'default': {}, 'default_'+sublime.platform(): {} }

        options_names = []
        options_paths = []
        options_desciptions = []

        options_names.append( [ "QUIT (Esc)", "End Edit Settings" ] )
        options_paths.append( ["Filler", "To keep the same index as options_names"] )
        options_desciptions.append( { "description": "You can press Esc, or select this option to end editing settings.\n" } )

        if setting_file is None:
            # log( 2, "run, self.setting_files.keys(): " + str( self.setting_files.keys() ) )
            self.is_main_panel = True

            for setting_file in sorted(self.setting_files.keys()):
                # log( 2, 'run, setting_file: ' + str( setting_file ) )

                if setting_file in self.syntax_names:
                    options_names.append( [ setting_file, "Syntax Settings" ] )

                else:
                    options_names.append( [ setting_file, "Package Settings" ] )

            options_start_index = 1
            options_to_move = \
            [
                [ default_preferences_file, "General Settings" ],
                [ this_view_file, "Preferences for this View only" ],
                [ distraction_free_file, "Preferences for Distraction Free Mode" ],
                [ current_syntax_file, "%s Syntax Specific Preferences" % self.current_syntax ],
                [ current_project_file, "Current Project Specific Preferences" ]
            ]

            for _option in options_to_move:
                option = [ _option[0], "Package Settings" ]

                if option in options_names:
                    options_names.remove( option )

                    options_names.insert( options_start_index, _option )
                    options_start_index += 1

        else:
            self.is_main_panel = False
            # log( 2, 'run, setting_file: ' + str( setting_file ) )

            options_names.append( [ "BACK (Open the Main Menu)", "Choose another Setting to Edit" ] )
            options_paths.append( ["Filler", "To keep the same index as options_names"] )
            options_desciptions.append( { "description": "Select this option to take another setting to edit.\n" } )

            for setting_name in sorted(self.get_setting_names(setting_file)):
                # log( 2, 'run, setting_name: ' + str( setting_name ) )

                option_path = [setting_file, setting_name]
                # log( 2, 'run, option_path: ' + str( option_path ) )

                options_paths.append( option_path )
                userValueAndDescription = self.getUserValueAndDescription(setting_file, setting_name)

                # log( 4, 'run, userValueAndDescription: ', json.dumps( userValueAndDescription, indent=4 ) )
                option_name = setting_file + '/' + setting_name

                # log( 2, 'run, option_name: ' + str( option_name ) )
                options_names.append( [ option_name, json.dumps( userValueAndDescription.get('value') ) ] )

                defaultValueAndDescription = self.getDefaultValueAndDescription(setting_file, setting_name)
                # log( 4, "run, defaultValueAndDescription: ", json.dumps( defaultValueAndDescription, indent=4 ) )

                options_desciptions.append( defaultValueAndDescription )

        self.help_view = HelperView(self.window, "preferences_editor_help", self.view.settings().get('always_show_helper_view', False))

        # Always create the main dictionary entry as it is only one key
        if main_function_key not in last_access:
            last_access[main_function_key] = 0

        self.help_view.show_panel()

        def on_highlighted(index):
            # log( 8, "run, on_highlighted, index: " + str( index ) )
            self.help_view.run_command("select_all")

            if index < len( options_desciptions ):
                # log( 8, "run, on_highlighted, index: " + str( options_desciptions[index] ) )
                self.help_view.run_command("insert", {"characters": options_desciptions[index]['description']})

            else:
                self.help_view.run_command("insert", {"characters": "Package Settings"})

            self.help_view.focus_begining()

        def done(index):
            # log( 8, "run, done, index:              " + str( index ) )
            # log( 8, "run, done, self.is_main_panel: " + str( self.is_main_panel ) )

            if index < 0:
                return self.shutdown()

            elif index == 0:
                self.shutdown()

            elif index == 1 and not self.is_main_panel:
                self.shutdown()
                self.window.run_command(command_name)

            elif self.is_main_panel:
                last_access[main_function_key] = index
                self.window.run_command(command_name, {"setting_file": options_names[index][0]})

            else:
                last_access[options_paths[index][0]] = index

                self.index = index
                self.change_value(options_paths, index)

        position = None
        # log( 4, "run, options_names: " + json.dumps( options_names, indent=4 ) )

        if self.is_main_panel:
            position = lambda: last_access[main_function_key]

        else:
            # Only create a dictionary entry for the remaining keys when it is required
            if self.setting_file not in last_access:
                last_access[self.setting_file] = 0

            position = lambda: last_access[self.setting_file]

        self.options_names = options_names
        self.preferences_selector = lambda: show_quick_panel(self.view, self.options_names, done, on_highlighted, position)
        self.preferences_selector()


