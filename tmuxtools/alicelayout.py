#!/usr/local/bin/python
# vim: set fileencoding=utf8 :
"""My custom tmux layout.

╭─────────┬──────┬─────────╮---
│         │ util │         │
│  shell  ├──────┤  shell  │  s
│         │ util │         │
╰─────────┴──────┴─────────╯---
 <--100--> <-60-> <--100-->

"""
import os, sh, sys
from collections import namedtuple
from sh import tmux
 
class Pane(object):
  _fields = ('id', 'index', 'width', 'height', 'active', 'start_command')

  def __init__(self, id, index, width, height, active, start_command):
    self.id = id
    self.index = int(index)
    self.width = width
    self.height = height
    self.active = (active == '1')
    self.start_command = start_command

  def __repr__(self):
    return ("Pane " if self.is_interactive else "Utility pane ") + self.id

  @property
  def is_interactive(self):
    return not self.start_command or self.start_command.startswith('reattach-to-user-namespace -l')

  def activate(self):
    tmux.selectp(t=self.id)
    self.active = True

def getPanes():
  format = ','.join('#{pane_%s}' % field for field in Pane._fields)
  for line in tmux.lsp(F=format):
    yield Pane(*line.strip().split(',', len(Pane._fields) - 1))
 
def getWindowSize():
  height, width = (int(x) for x in
      tmux.display("-p", "#{window_height},#{window_width}").strip().split(","))
  return height, width
 
def layoutChecksum(l):
  csum = 0
  for c in l:
    csum = (csum >> 1) + ((csum & 1) << 15) + ord(c)
    csum = csum & 0xFFFF
  return csum

def partition(l, n):
  """Partition l into n partitions of approximately equal size."""
  return [l[i*len(l)//n:(i+1)*len(l)//n] for i in range(n)]

def reorderPanes(orderedPanes):
  """Reorders panes in tmux to match the given order."""
  activePane = [p for p in orderedPanes if p.active][0]
  currentOrder = sorted(orderedPanes, key=lambda p : p.index)
  for i in range(len(orderedPanes)):
    current = currentOrder[i]
    desired = orderedPanes[i]
    if current != desired:
      swapIndex = currentOrder.index(desired)
      assert swapIndex > i
      tmux.swapp(s=current.id, t=desired.id)
      currentOrder[i] = desired
      desired.index = i
      currentOrder[swapIndex] = current
      current.index = swapIndex
  activePane.activate()
   
def alicelayout():
  windowHeight, windowWidth = getWindowSize()

  if windowWidth < 161:
    # No space for clever formatting
    tmux.selectl('even-vertical')
    sys.exit(0)
   
  allPanes = list(getPanes())
  allPanes.sort(key=lambda p : p.index)

  mainPanes = [pane for pane in allPanes if pane.is_interactive]
  utilityPanes = [pane for pane in allPanes if not pane.is_interactive]

  mainColumns = min(len(mainPanes), max((windowWidth - (60 if utilityPanes else 0)) // 101, 1))
  panesByColumn = partition(mainPanes, mainColumns)
  if utilityPanes:
    panesByColumn.insert(1, utilityPanes)

    reorderPanes([p for column in panesByColumn for p in column])

  formatComponents = []
  x = 0
  for c, panes in enumerate(panesByColumn):
    if c == 0:
      width = windowWidth - 101 * (mainColumns - 1) - (61 if utilityPanes else 0)
    elif c == 1 and utilityPanes:
      width = 60
    else:
      width = 100
    fmt = "%dx%d,%d,0" % (width, windowHeight, x)
    if len(panes) > 1:
      subcomponents = []
      y = 0
      for r, pane in enumerate(panes):
        y1 = (r+1)*(windowHeight + 1) // len(panes) - 1
        height = y1 - y
        subfmt = "%dx%d,%d,%d" % (width, height, x, y)
        subcomponents.append(subfmt)
        y += height + 1
      fmt = "%s[%s]" % (fmt, ",".join(subcomponents))
    formatComponents.append(fmt)
    x += width + 1
   
  formatString = "%dx%d,0,0{%s}" % (windowWidth, windowHeight, ",".join(formatComponents))
  formatString = "%04x,%s" % (layoutChecksum(formatString), formatString)
  tmux.selectl(formatString)
  tmux.refresh()

