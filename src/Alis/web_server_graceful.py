import multiprocessing
import uvicorn
import web_server
import time

# This function will be run in a separate process and will listen for a shutdown event.
def run_web_server_with_shutdown(web_animation_queue, current_settings, settings_lock, interface_web_queue, web_interface_queue, shutdown_event):
    web_server.app.state.web_animation_queue = web_animation_queue
    web_server.app.state.web_show_queue = None  # Set if needed
    web_server.app.state.current_settings = current_settings
    web_server.app.state.settings_lock = settings_lock
    web_server.app.state.interface_web_queue = interface_web_queue
    web_server.app.state.web_interface_queue = web_interface_queue

    config = uvicorn.Config("web_server:app", host="0.0.0.0", port=8000, reload=False)
    server = uvicorn.Server(config)

    # Start the server in a thread so we can monitor the shutdown_event
    import threading
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for shutdown_event to be set
    while not shutdown_event.is_set() and not server.should_exit:
        time.sleep(0.2)
    # Trigger graceful shutdown
    server.should_exit = True
    server_thread.join(timeout=5)
