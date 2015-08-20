
from __future__ import division
import collections

import numpy

import logic


class Schematic(object):
    """A collection of entities laid out onto a schematic."""

    def __init__(self):
        self.entities = set()

    def draw(self, context, selected_entities=(), **kwargs):
        default_draw_connections = kwargs.get('draw_terminals', False)

        for entity in self.entities:
            if entity in selected_entities:
                kwargs['draw_terminals'] = True
            else:
                kwargs['draw_terminals'] = default_draw_connections

            context.save()
            entity.draw(context, selected=entity in selected_entities, **kwargs)
            context.restore()

            """
            context.rectangle(*entity.get_bbox())
            context.set_source_rgb(0, 1, 1)
            context.set_line_width(.2)
            context.stroke()
            """

    def add_entity(self, entity):
        entity.reset()
        self.entities.add(entity)

    def add_entities(self, entities):
        self.entities.update(entities)

    def remove(self, entity):
        assert entity in self.entities

        if isinstance(entity, logic.Component):

            # Disconnect terminals from nets
            modified_nets = set()
            for term in entity.terminals.itervalues():
                if term.net:
                    term.net.remove(term)
                    modified_nets.add(term.net)
                    term.net = None

            # Any nets that should be deleted?
            for net in modified_nets:
                if len(list(net.terminals)) < 2:
                    self.remove(net)

        elif isinstance(entity, logic.Net):
            for term in entity.terminals:
                term.net = None
                term.input = None

        self.entities.remove(entity)
        self.update()

    def connect(self, *terms):
        net = None
        for i in range(1, len(terms)):
            net = self._connect2(terms[i], terms[i-1], net)

    def _connect2(self, term1, term2, net=None):

        def get_term_and_net(term):
            if isinstance(term, logic.Component):
                assert len(term.terminals) == 1
                term = term.terminals.values()[0]

            if isinstance(term, logic.components.Terminal):
                return term, term.net
            elif isinstance(term, tuple):
                return term, None
            else:
                assert False

        term1, net1 = get_term_and_net(term1)
        term2, net2 = get_term_and_net(term2)

        n_disconnected = [net1, net2].count(None)

        if n_disconnected == 2:
            if net is None:
                net = logic.Net(term1, term2)
                self.entities.add(net)
            else:
                 net.connect(term1, term2)
            return net
        elif n_disconnected == 1 or net1 == net2:
            net.connect(term1, term2)
            return net
        elif n_disconnected == 0:
            self.entities.remove(net1)
            self.entities.remove(net2)
            new_net = logic.Net.combine(net1, term1, net2, term2)
            self.entities.add(new_net)
            return new_net

    @property
    def components(self):
        return filter(lambda e: isinstance(e, logic.Component), self.entities)

    @property
    def nets(self):
        return filter(lambda e: isinstance(e, logic.Net), self.entities)

    def validate(self):

        all_terminals = set()
        for component in self.components:
            component.validate()

            if isinstance(component, logic.Component):
                for term in component.terminals.itervalues():
                    assert term.net in self.entities or term.net is None

                all_terminals.update(component.terminals.values())

        for net in self.nets:

            if isinstance(net, logic.Net):
                for term in net.terminals:
                    assert term in all_terminals

    def reset(self):
        for entity in self.entities:
            entity.reset()

    def update(self):

        to_visit = collections.deque(self.entities)
        while to_visit:
            item = to_visit.popleft()

            if isinstance(item, logic.Net):
                was_updated = item.update()
                if was_updated:
                    to_visit.extend(set([term.component for term in item.terminals]))

            elif isinstance(item, logic.Component):
                prev_term_outs = item.get_output_dict()
                item.update()
                cur_term_outs = item.get_output_dict()
                for name, term in item.terminals.iteritems():
                    if prev_term_outs[name] != cur_term_outs[name]:
                        to_visit.append(term.net)

            elif item is not None:
                print item
                raise RuntimeError()

    def get_bbox(self):
        left = top = float('inf')
        right = bot = float('-inf')
        for item in list(self.entities) + list(self.nets):
            bbox  = item.get_bbox()
            x1, y1 = bbox[0], bbox[1]
            x2, y2 = bbox[0]+bbox[2], bbox[1]+bbox[3]
            left  = min(left,  x1, x2)
            top   = min(top,   y1, y2)
            right = max(right, x1, x2)
            bot   = max(bot,   y1, y2)
        return (left, top, right-left, bot-top)

    def entity_at_pos(self, pos):
        for entity in self.entities:
            if entity.point_intersect(pos):
                return entity
        return None

    def get_closest_terminal(self, pos, search_dist=float('inf')):
        pos = numpy.array(pos)

        closest_dist = float('inf')
        closest_term = None
        for component in self.components:
            for term in component.terminals.itervalues():
                dist = numpy.linalg.norm(term.absolute_pos - pos)
                if dist <= closest_dist:
                    closest_dist = dist
                    closest_term = term
        if closest_dist > search_dist:
            return None
        else:
            return closest_term
