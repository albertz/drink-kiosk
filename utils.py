
import os


def better_repr(obj):
    """
    Replacement for `repr`, which is deterministic (e.g. sorted key order of dict),
    and behaves also nicer for diffs, or visual representation.

    :param object obj:
    :rtype: str
    """
    if isinstance(obj, dict):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "{\n%s}" % "".join(
                ["%s: %s,\n" % (better_repr(key), better_repr(value)) for (key, value) in sorted(obj.items())])
        return "{%s}" % ", ".join(
            ["%s: %s" % (better_repr(key), better_repr(value)) for (key, value) in sorted(obj.items())])
    if isinstance(obj, set):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "{\n%s}" % "".join(["%s,\n" % better_repr(value) for value in sorted(obj)])
        return "{%s}" % ", ".join([better_repr(value) for value in sorted(obj)])
    if isinstance(obj, list):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "[\n%s]" % "".join(["%s,\n" % better_repr(value) for value in obj])
        return "[%s]" % ", ".join([better_repr(value) for value in obj])
    if isinstance(obj, tuple):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "(\n%s)" % "".join(["%s,\n" % better_repr(value) for value in obj])
        if len(obj) == 1:
            return "(%s,)" % better_repr(obj[0])
        return "(%s)" % ", ".join([better_repr(value) for value in obj])
    # Generic fallback.
    return repr(obj)


def init_ipython_kernel():
    """
    You can remotely connect to this IPython kernel. See the output on stdout.

    https://github.com/ipython/ipython/issues/8097
    https://stackoverflow.com/questions/29148319/provide-remote-shell-for-python-script
    """
    #
    try:
        import IPython.kernel.zmq.ipkernel
        from IPython.kernel.zmq.ipkernel import Kernel
        from IPython.kernel.zmq.heartbeat import Heartbeat
        from IPython.kernel.zmq.session import Session
        from IPython.kernel import write_connection_file
        import zmq
        from zmq.eventloop import ioloop
        from zmq.eventloop.zmqstream import ZMQStream
        # IPython.kernel.zmq.ipkernel.signal = lambda sig, f: None  # Overwrite.
    except ImportError as e:
        print("IPython import error, cannot start IPython kernel. %s" % e)
        return
    import atexit
    import socket
    import logging
    import threading

    # Do in mainthread to avoid history sqlite DB errors at exit.
    # https://github.com/ipython/ipython/issues/680
    assert isinstance(threading.currentThread(), threading._MainThread)
    try:
        connection_file = "kernel-%s.json" % os.getpid()
        def cleanup_connection_file():
            try:
                os.remove(connection_file)
            except (IOError, OSError):
                pass
        atexit.register(cleanup_connection_file)

        logger = logging.Logger("IPython")
        logger.addHandler(logging.NullHandler())
        session = Session(username=u'kernel')

        context = zmq.Context.instance()
        ip = socket.gethostbyname(socket.gethostname())
        transport = "tcp"
        addr = "%s://%s" % (transport, ip)
        shell_socket = context.socket(zmq.ROUTER)
        shell_port = shell_socket.bind_to_random_port(addr)
        iopub_socket = context.socket(zmq.PUB)
        iopub_port = iopub_socket.bind_to_random_port(addr)
        control_socket = context.socket(zmq.ROUTER)
        control_port = control_socket.bind_to_random_port(addr)

        hb_ctx = zmq.Context()
        heartbeat = Heartbeat(hb_ctx, (transport, ip, 0))
        hb_port = heartbeat.port
        heartbeat.start()

        shell_stream = ZMQStream(shell_socket)
        control_stream = ZMQStream(control_socket)

        kernel = Kernel(session=session,
                        shell_streams=[shell_stream, control_stream],
                        iopub_socket=iopub_socket,
                        log=logger)

        write_connection_file(connection_file,
                              shell_port=shell_port, iopub_port=iopub_port, control_port=control_port, hb_port=hb_port,
                              ip=ip)

        print("To connect another client to this IPython kernel, use: ",
              "ipython console --existing %s" % connection_file)
    except Exception as e:
        print("Exception while initializing IPython ZMQ kernel. %s" % e)
        return

    def start_kernel():
        print("IPython: Start kernel now.")
        kernel.start()

    def ipython_thread():
        import asyncio
        loop = asyncio.new_event_loop()
        loop.call_soon(start_kernel)
        print("IPython event loop:", loop)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass

    thread = threading.Thread(target=ipython_thread, name="IPython kernel")
    thread.daemon = True
    thread.start()
