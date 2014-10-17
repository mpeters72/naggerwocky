#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Naggerwocky
# naggerwocky.py
# Shun the frumious shell called Bash

# Copyright (c) 2013 Mike Peters <mike@ice2o.com>
#
# A Jabber Bot to communicate with Nagios
#
# Began as a hack of notification-jabber.py by Alexei Andrushievich <vint21h@vint21h.pp.ua>
#
# Naggerwocky is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# TODO: Move to config file
DEBUG = True
MSG_MAXLEN = 10000
MSG_CHUNKLEN = 5000

import sys

try:
    import os
    import time
    import warnings
    import ConfigParser
    from optparse import OptionParser
    # strong hack to supress deprecation warnings called by xmpppy using md5, sha modules and socket.ssl() method
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import xmpp
    from xmpp.protocol import *
except ImportError, err:
    sys.stderr.write("ERROR: Couldn't load module. %s\n" % err)
    sys.exit(-1)

__all__ = ['main', ]

# metadata
VERSION = (0, 0, 1)
__version__ = '.'.join(map(str, VERSION))


def parse_options():
    """
    Commandline options arguments parsing.
    """

    # build options and help
    version = "%%prog %s" % __version__
    parser = OptionParser(version=version)
    parser.add_option(
        "-r", "--recipient", action="store", dest="recipient",
        type="string", default="", metavar="RECIPIENT",
        help="message recipient Jabber ID"
    )
    parser.add_option(
        "-R", "--room", action="store", dest="room",
        type="string", default="", metavar="ROOM",
        help="send message to this room"
    )
    parser.add_option(
        "-b", "--bot", action="store_true", dest="bot",
        metavar="BOT",
        help="run as a bot"
    )
    parser.add_option(
        "-m", "--message", metavar="MESSAGE", action="store",
        type="string", dest="message", default="", help="message text"
    )
    parser.add_option(
        "-c", "--config", metavar="CONFIG", action="store",
        type="string", dest="config", default="/etc/nagios/naggerwocky.ini",
        help="path to config file"
    )
    parser.add_option(
        "-q", "--quiet", metavar="QUIET", action="store_true",
        default=False, dest="quiet", help="be quiet"
    )

    options = parser.parse_args(sys.argv)[0]

    # check mandatory command line options supplied
    if not options.bot:
      mandatories = [ "recipient", "message", ]
      if not all(options.__dict__[mandatory] for mandatory in mandatories):
        parser.error("Required command line option missing")

    return options


def parse_config(options):
    """
    Get connection settings from config file.
    """

    if os.path.exists(options.config):
        config = ConfigParser.ConfigParser()
        try:
            config.read(options.config)
        except Exception:
            if not options.quiet:
                sys.stderr.write("ERROR: Config file read %s error." % options.config)
            sys.exit(-1)

        try:
            configdata = {
                'jid': config.get('JABBER', 'jid'),
                'password': config.get('JABBER', 'password'),
                'resource': config.get('JABBER', 'resource'),
                'statusfile': config.get('JABBER', 'statusfile'),
                'room': config.get('JABBER', 'room'),
            }
        except ConfigParser.NoOptionError, err:
            sys.stderr.write("ERROR: Config file missing option error. %s\n" % err)
            sys.exit(-1)

        # check mandatory config options supplied
        mandatories = ["jid", "password", ]
        if not all(configdata[mandatory] for mandatory in mandatories):
            if not options.quiet:
                sys.stdout.write("Required config option missing\n")
            sys.exit(0)

        return configdata
    else:
        if not options.quiet:
            sys.stderr.write("ERROR: Config file %s does not exist\n" % options.config)
        sys.exit(0)


def send_message(config, options):
    """
    Connect to server and send message.
    """

    jid = xmpp.JID(config['jid'])  # JID object
    client = xmpp.Client(jid.getDomain(), debug=[])
    try:
        client.connect()
        client.auth(jid.getNode(), config['password'], config['resource'])
        client.sendInitPresence()
    except Exception, err:
        if not options.quiet:
            sys.stdout.write("ERROR: Couldn't connect or auth on server. %s\n" % err)
        sys.exit(-1)
    xmessage = xmpp.Message(options.recipient, options.message)
    xmessage.setAttr('type', 'chat')
    try:
        client.send(xmessage)
    except Exception, err:
        if not options.quiet:
            sys.stdout.write("ERROR: Couldn't send message. %s\n" % err)
        sys.exit(-1)


class NagStatus:
    def __init__(self, statusfile):
        try:
            if os.path.exists(statusfile):
                self.file = open(statusfile, 'r')
        except Exception, err:
            sys.stdout.write("ERROR: Failed to open Nagios status file. %s\n" % err)


    def __load_hosts__(self):
        self.__load_status__()
        hosts = []
        for block in self.fullstatus:
          if block[0].strip().startswith('hoststatus'):
            host = {}
            for b in block:
              try:
                h = b.split('=')
                host[h[0]] = h[1]
              except:
                pass
            hosts.append(host)

        self.hosts = hosts


    def __load_services__(self):
        self.__load_status__()
        services = []
        for block in self.fullstatus:
          if block[0].strip().startswith('servicestatus'):
            service = {}
            for b in block:
              try:
                s = b.split('=')
                service[s[0]] = s[1]
              except:
                pass
            services.append(service)

        self.services = services


    def __load_status__(self):
        # 2 states, start when outside block, block when inside
        state = 'start'
        blocks = []
        block = []
        for line in self.file:
          if state == 'start':
            # If {, start a block and append the line
            if '{' in line:
              state = 'block'
              block.append(line.replace('\t', '').replace('\n', ''))
            else:
              pass
          else:
            # If already in block state, just append the line
            block.append(line.replace('\t', '').replace('\n', ''))
            # if }, append the block to blocks and clear block and go in start state
            if '}' in line:
              state = 'start'
              blocks.append(block)
              block = []
        
        self.fullstatus = blocks


    def getService(self, searchname):
      self.__load_services__()
      out = []
      for s in self.services:
        if searchname == "ALL":
          if (s['active_checks_enabled'] == '1' or s['passive_checks_enabled'] == '1'):
            info = {}
            info['host_name'] = s['host_name']
            info['service_description'] = s['service_description']
            info['plugin_output'] = s['plugin_output']
            out.append(info)
        else:
          name = s['host_name']
          if (s['active_checks_enabled'] == '1' or s['passive_checks_enabled'] == '1') and name.lower().find(searchname.lower()) >= 0:
            info = {}
            info['host_name'] = s['host_name']
            info['service_description'] = s['service_description']
            info['plugin_output'] = s['plugin_output']
            out.append(info)
      return out


    def getHost(self, searchname):
      self.__load_hosts__()
      out = []
      for h in self.hosts:
        if searchname == "ALL":
          if (h['active_checks_enabled'] == '1' or h['passive_checks_enabled'] == '1'):
            out.append(h)
        else:
          hostname = h['host_name']
          if (h['active_checks_enabled'] == '1' or h['passive_checks_enabled'] == '1') and hostname.lower().find(searchname.lower()) >= 0:
            out.append(h)
      return out


    def getForStatus(self, status):
      self.__load_services__()
      out = []
      for s in self.services:
        state = s['current_state']
        if s['active_checks_enabled'] == '1' or s['passive_checks_enabled'] == '1':
          if state == '%s' % status:
            c = "%s: %s: %s" % (s['host_name'], s['service_description'], s['plugin_output'])
            out.append(c)
      return out


    def getCritical(self):
      return self.getForStatus(2)


    def getOK(self):
      return self.getForStatus(0)


    def getWarn(self):
      return self.getForStatus(1)


    def getStatus(self):
      OK = 0
      WARN = 0
      CRIT = 0
      UNKNOWN = 0

      self.__load_services__()
      for s in self.services:
        state = s['current_state']
        if s['active_checks_enabled'] == '1' or s['passive_checks_enabled'] == '1':
          if state == '0':
            OK += 1
          elif state == '1':
            WARN += 1
          elif state == '2':
            CRIT += 1
          else: 
            UNKNOWN += 1
      
      status = {}
      status['OK'] = OK
      status['WARN'] = WARN
      status['CRIT'] = CRIT
      status['UNKNOWN'] = UNKNOWN

      return status


class Naggerwocky:
    def __init__(self, config, options):
        jid = xmpp.JID(config['jid'])  # JID object
        client = xmpp.Client(jid.getDomain(), debug=[])
        try:
            client.connect()
            client.auth(jid.getNode(), config['password'], config['resource'])
            client.RegisterHandler('message', self.messageCB)
            client.sendInitPresence(requestRoster=0)
            if len(config['room']) > 1 or len(options.room) > 1: # TODO: Need better validation of room
              self.room = config['room']
              client.send(xmpp.Presence(to='{0}/{1}'.format(self.room, config['jid'])))
            else:
              self.room = None

            # plugins
            # disco - needed by commands
            # warning: case of "plugin" method names are important!
            # to attach a command to Commands class, use .plugin()
            # to attach anything to Client class, use .PlugIn()
            self.disco = xmpp.browser.Browser()
            self.disco.PlugIn(client)
            self.disco.setDiscoHandler({
                    'info': {
                            'ids': [{
                                    'category': 'client',
                                    'type': 'pc',
                                    'name': 'Naggerwocky'
                                    }],
                            'features': [NS_DISCO_INFO],
                            }
                    })

            self.commands = xmpp.commands.Commands(self.disco)
            self.commands.PlugIn(client)

        except Exception, err:
            if not options.quiet:
                sys.stdout.write("ERROR: Couldn't connect or auth on server. %s\n" % err)
        self.client = client
        self.options = options
        self.config = config

        # Debuggle
        self.sendMessage(options.recipient, options.message)


    def messageCB(self, con, message):
        """ Handle messages """
        msg = message.getBody()
        sender = message.getFrom()

        if not self.room:
          send_to = sender
        else:
          send_to = self.room

        # Debuggling
        print msg
        print sender
        print message

        try:
            if msg.lower().replace(' ', '') == "help":
                msg = "Hi! I'm the Naggerwocky Nagios Chat Bot. You can use and abuse me by sending the following commands:\n\n \
              status - Display the current overall alert status\n \
              critical - Display the current critical alerts\n \
              warn - Display the current warning alerts\n \
              ok - Display the checks with a status of OK\n \
              host <full or partial hostname> - show information about the specified host(s)\n \
              service <full or partial hostname> - show service information for the specified host(s)\n"

            elif msg.lower().replace(' ', '') == "status":
                nagios = NagStatus(self.config['statusfile'])
                s = nagios.getStatus()
                msg = "Current Status:\n\tCRITICAL: %s\n\tWARNING: %s\n\tUNKNOWN: %s\n\tOK: %s" % (s['CRIT'], s['WARN'], s['UNKNOWN'], s['OK'])

            elif msg.lower().replace(' ', '') == "critical":
                nagios = NagStatus(self.config['statusfile'])
                critical = nagios.getCritical()
                out = ''
                for c in critical:
                  out = "%s\n%s" % (out, c)
                msg = "Critical Services (%s): %s" % (len(critical), out)

            elif msg.lower().replace(' ', '') == "warn":
                nagios = NagStatus(self.config['statusfile'])
                warn = nagios.getWarn()
                out = ''
                for w in warn:
                  out = "%s\n%s" % (out, w)
                msg = "Warning Services (%s): %s" % (len(warn), out)

            elif msg.lower().replace(' ', '') == "ok":
                nagios = NagStatus(self.config['statusfile'])
                ok = nagios.getOK()
                out = ''
                for o in ok:
                  out = "%s\n%s" % (out, o)
                msg = "OK Services (%s): %s" % (len(ok), out)

            elif msg.lower().find("host ") == 0:
                nagios = NagStatus(self.config['statusfile'])
                name = msg.replace('host ', '').replace(' ', '')

                if len(name) > 0:
                  hosts = nagios.getHost(name)
                  out = ''

                  for h in hosts:
                    out = "%s\n\n======= %s =========" % (out, h['host_name'].upper())
                    for k,v in h.items():
                      out = "%s\n%s: %s" % (out, k, v)

                  msg = "Hosts:\n%s" % (out)
                else:
                  msg = "Invalid host name"

            elif msg.lower().find("service ") == 0:
                nagios = NagStatus(self.config['statusfile'])
                name = msg.replace('service ', '').replace(' ', '')

                if len(name) > 0:
                  services = nagios.getService(name)
                  out = ''

                  for s in services:
                    out = "%s\n\n======= %s %s =========" % (out, s['host_name'], s['service_description'].upper())
                    for k,v in s.items():
                      out = "%s\n%s: %s" % (out, k, v)

                  msg = "Services:\n%s" % (out)
                else:
                  msg = "Invalid service name"
              
            self.sendMessage(send_to, msg)

        except Exception, err:
            if DEBUG:
                self.sendMessage(send_to, err)
            else:
                pass


    def loop(self):
        """ Do nothing except handling new xmpp stanzas. """
        try:
            while self.client.Process(1):
                pass
        except KeyboardInterrupt:
                pass


    def sendMessage(self, recipient, message):
        message = '%s' % message
        if len(message) < MSG_MAXLEN:
          if len(message) > MSG_CHUNKLEN:
            count = MSG_CHUNKLEN
            msg = [''.join(x) for x in zip(*[list(message[z::count]) for z in range(count)])]

            xmessage = xmpp.Message(recipient, "===============STARTING LONG MESSAGE==============")
            for m in msg:
              xmessage = xmpp.Message(recipient, m)
              self.client.send(xmessage)
              time.sleep(2)
            xmessage = xmpp.Message(recipient, "===============END OF LONG MESSAGE==============")
          else:
            xmessage = xmpp.Message(recipient, message)
        else:
          xmessage = xmpp.Message(recipient, "===============MESSAGE EXCEEDS MAXIMUM SIZE==============")

        if self.room:
          xmessage.setAttr('type', 'groupchat')
        else:
          xmessage.setAttr('type', 'chat')
        self.client.send(xmessage)


def main():
    """
    Program main.
    """

    options = parse_options()
    config = parse_config(options)

    #send_message(parse_config(options), options)

    bot = Naggerwocky(config, options)
    if options.bot:
      bot.loop()
    else:
      bot.sendMessage(options.recipient, options.message)

    sys.exit(0)

if __name__ == "__main__":
    main()
