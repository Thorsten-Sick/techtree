#!/usr/bin/env python
# Copyright (C) 2010-2014 Avira Operations.
# See the file 'LICENSE' for copying permission.
# Released under the GPL V3.

# By Thorsten Sick @ Avira
# thorsten.sick@avira.com
# http://www.avira.com

# Concept of parsing rst files from here:
# https://github.com/jbremer/monitor/blob/master/utils/process.py

import argparse
import os
import copy
import docutils.nodes
import docutils.utils
import docutils.parsers.rst
import subprocess

class CreateTree(object):

    def __init__(self, data_dir, output):
        """

        :param data_dir: Directory containing rst files
        :param output: output .dot file
        :return:
        """
        self.data_dir = data_dir
        self.output = output

        self.nodes = {}


    def parser_settings(self):
        components = docutils.parsers.rst.Parser,
        settings = docutils.frontend.OptionParser(components=components)
        return settings.get_default_values()

    def read_document(self, tech_path):
        doc = docutils.utils.new_document(os.path.basename(tech_path), self.parser_settings())
        parser = docutils.parsers.rst.Parser()
        parser.parse(open(tech_path, 'rb').read().decode("utf-8"), doc)
        return parser


    def helper_parse_bullet_points(self, text):
        """
        :param text: Parse bullet points
        :return:
        """
        ret = {"bullet_points":[]}
        for line in text.split('\n'):
            if not line.startswith('*'):
                raise Exception('Every line of the bullet point list should start with an asterisks: %r.' % line)
            value = line[1:]

            ret["bullet_points"].append(value.strip())
        return ret

    def helper_parse_text(self, text):
        ret = {"text": text}
        return ret

    def _parse_depends_on(self, text):
        return self.helper_parse_bullet_points(text)

    def _parse_synergy_with(self, text):
        return self.helper_parse_bullet_points(text)

    def _parse_responsible(self, text):
        return self.helper_parse_bullet_points(text)

    def _parse_ap(self, text):
        return self.helper_parse_text(text)

    def _parse_description(self, text):
        return self.helper_parse_text(text)

    def _parse_spin_off(self, text):
        return self.helper_parse_text(text)

    def _parse_duration(self, text):
        return self.helper_parse_text(text)

    def _parse_paragraph(self, paragraph, literal_block):
        if not isinstance(paragraph, docutils.nodes.paragraph):
            raise Exception('Node must be a paragraph.')
        if not isinstance(literal_block, docutils.nodes.literal_block):
            raise Exception('Child node must be a literal block in: %s', paragraph)
        key = paragraph.astext().replace(':', '').lower().replace(" ", "_")
        if not hasattr(self, '_parse_' + key):
            raise Exception('No parser known for the %r section.' % key)
        return key, getattr(self, '_parse_' + key)(literal_block.astext())

    def normalize(self, doc):
        global_values, start = {}, 0

        # Empty ap file?
        if not doc.document.children:
            return

        while isinstance(doc.document.children[start],
            docutils.nodes.paragraph):
            try:
                children = doc.document.children
                key, value = self._parse_paragraph(children[start],
                children[start+1])
            except Exception as e:
                raise Exception('Error parsing global node: %s' % e.message)
            global_values[key] = value
            start += 2

        for entry in doc.document.ids.values():
            if not isinstance(entry.children[0], docutils.nodes.title):
                raise Exception('Node must be a title.')
            taskname = entry.children[0].astext()
            children = entry.children
            row = copy.deepcopy(global_values)
            row['taskname'] = taskname
            print taskname
            for x in xrange(1, len(children), 2):
                #try:
                key, value = self._parse_paragraph(children[x], children[x+1])
                if key in row:
                    self._prevent_overwrite(key, value, global_values)
                    row[key].update(value)
                else:
                    row[key] = value
                #except Exception as e:
                #    raise Exception('Error parsing node of api %r: %s' % (taskname, e.message))

            print row

            # TODO: Add defaults, fix errors

            yield row

    def norm_taskname(self, name):
        return name.lower().replace(" ","_").replace("-","_")

    def create_dot(self):
        def get_node_from_name(taskname):
            for node in self.nodes:
                if self.nodes[node]["taskname"] == taskname:
                    return node
            return None

        def get_node_format(node):
            if not "spin_off" in self.nodes[node]:
                return ""
            if "mark_red" in self.nodes[node]["spin_off"]["text"].lower():
                return "color=\"red\""
            if "mark_green" in self.nodes[node]["spin_off"]["text"].lower():
                return "color=\"green\""
            return ""


        res = "digraph techtree { \n"
        # Adding nodes
        for node in self.nodes:
            res += "%s [label = \"%s\" %s]\n" % (node, self.nodes[node]["taskname"], get_node_format(node))

        # Adding links
        for node in self.nodes:
            if "depends_on" in self.nodes[node]:
                for dep in self.nodes[node]["depends_on"]["bullet_points"]:
                    res += "%s -> %s;\n" %(get_node_from_name(dep), node)

        # Synergy links
        for node in self.nodes:
            if "synergy_with" in self.nodes[node]:
                for dep in self.nodes[node]["synergy_with"]["bullet_points"]:
                    res += "%s -> %s[style=dotted];\n" %(get_node_from_name(dep), node)


        res += "}"
        return res

    def process(self):

        self.nodes = {}

        #sigs = []
        for tech_file in os.listdir(self.data_dir):
            if not tech_file.endswith('.rst'):
                continue
            tech_path = os.path.join(self.data_dir, tech_file)
            for tech in self.normalize(self.read_document(tech_path)):
                self.nodes[self.norm_taskname(tech["taskname"])] = tech
        with open(self.output+".dot", "wt") as fh:
            fh.write(self.create_dot())
        subprocess.call(["dot", "-Tsvg", "-o"+self.output, self.output+".dot"])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data_directory', type=str, help='Path to data directory.')
    parser.add_argument('--output', type=str, help='output file name', default ="techtree.svg")
    args = parser.parse_args()

    ct = CreateTree(args.data_directory, args.output)
    ct.process()
