"""Long-lived services that bridge the OS to the Qt event loop.

Both the global hotkey hook and the microphone monitor deliver their events on
foreign threads. Everything in this package converts those into Qt signals so
widget code is only ever touched from the GUI thread.
"""
