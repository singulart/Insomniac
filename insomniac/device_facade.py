from enum import Enum, unique
from random import uniform
from re import search

from insomniac.utils import *

# How long we're waiting until UI element appears (loading content + animation)
UI_TIMEOUT_LONG = 5
UI_TIMEOUT_SHORT = 1


def create_device(is_old, device_id, app_id):
    print("Using uiautomator v" + ("1" if is_old else "2"))
    try:
        return DeviceFacade(is_old, device_id, app_id)
    except ImportError as e:
        print(COLOR_FAIL + str(e) + COLOR_ENDC)
        return None


class DeviceFacade:
    deviceV1 = None  # uiautomator
    deviceV2 = None  # uiautomator2
    width = None
    height = None
    device_id = None
    app_id = None

    def __init__(self, is_old, device_id, app_id):
        self.device_id = device_id
        self.app_id = app_id
        if is_old:
            try:
                import uiautomator
                self.deviceV1 = uiautomator.device if device_id is None else uiautomator.Device(device_id)
            except ImportError:
                raise ImportError("Please install uiautomator: pip3 install uiautomator")
        else:
            try:
                import uiautomator2
                self.deviceV2 = uiautomator2.connect() if device_id is None else uiautomator2.connect(device_id)
            except ImportError:
                raise ImportError("Please install uiautomator2: pip3 install uiautomator2")

    def is_old(self):
        return self.deviceV1 is not None

    def find(self, *args, **kwargs):
        if self.deviceV1 is not None:
            import uiautomator
            try:
                view = self.deviceV1(*args, **kwargs)
            except uiautomator.JsonRPCError as e:
                raise DeviceFacade.JsonRpcError(e)
            return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
        else:
            import uiautomator2
            try:
                view = self.deviceV2(*args, **kwargs)
            except uiautomator2.JSONRPCError as e:
                raise DeviceFacade.JsonRpcError(e)
            return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

    def back(self):
        if self.deviceV1 is not None:
            self.deviceV1.press.back()
        else:
            self.deviceV2.press("back")

    def screen_click(self, place):
        w, h = self._get_screen_size()
        if place == DeviceFacade.Place.RIGHT:
            left = int(w * 3 / 4)
            top = int(h / 2)
        else:
            return

        if self.deviceV1 is not None:
            self.deviceV1.click(left, top)
        else:
            self.deviceV2.click(left, top)

    def screenshot(self, path):
        if self.deviceV1 is not None:
            self.deviceV1.screenshot(path)
        else:
            self.deviceV2.screenshot(path)

    def dump_hierarchy(self, path):
        if self.deviceV1 is not None:
            xml_dump = self.deviceV1.dump()
        else:
            xml_dump = self.deviceV2.dump_hierarchy()

        with open(path, 'w', encoding="utf-8") as outfile:
            outfile.write(xml_dump)

    def is_screen_on(self):
        return self.get_info()["screenOn"]

    def press_power(self):
        if self.deviceV1 is not None:
            self.deviceV1.press.power()
        else:
            self.deviceV2.press("power")

    def is_screen_locked(self):
        cmd = f"adb {'' if self.device_id is None else ('-s '+ self.device_id)} shell dumpsys window"

        cmd_res = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, shell=True, encoding="utf8")
        data = cmd_res.stdout.strip()
        flag = search("mDreamingLockscreen=(true|false)", data)
        return True if flag.group(1) == "true" else False

    def is_alive(self):
        if self.deviceV1 is not None:
            return self.deviceV1.alive()
        else:
            return self.deviceV2._is_alive()

    def wake_up(self):
        """ Make sure agent is alive or bring it back up before starting. """
        attempts = 0
        while not self.is_alive() and attempts < 5:
            self.get_info()
            attempts += 1

    def unlock(self):
        self.swipe(DeviceFacade.Direction.TOP, 0.8)
        if self.is_screen_locked():
            self.swipe(DeviceFacade.Direction.RIGHT, 0.8)

    def screen_off(self):
        if self.deviceV1 is not None:
            self.deviceV1.screen.off()
        else:
            self.deviceV2.screen_off()

    def swipe(self, direction: "DeviceFacade.Direction", scale=0.5):
        """Swipe finger in the `direction`.
        Scale is the sliding distance. Default to 50% of the screen width
        """

        if self.deviceV1 is not None:
            def _swipe(_from, _to):
                self.deviceV1.swipe(_from[0], _from[1], _to[0], _to[1])

            lx, ly = 0, 0
            rx, ry = self._get_screen_size()

            width, height = rx - lx, ry - ly

            h_offset = int(width * (1 - scale)) // 2
            v_offset = int(height * (1 - scale)) // 2

            left = lx + h_offset, ly + height // 2
            up = lx + width // 2, ly + v_offset
            right = rx - h_offset, ly + height // 2
            bottom = lx + width // 2, ry - v_offset

            if direction == DeviceFacade.Direction.TOP:
                _swipe(bottom, up)
            elif direction == DeviceFacade.Direction.RIGHT:
                _swipe(left, right)
            elif direction == DeviceFacade.Direction.LEFT:
                _swipe(right, left)
            elif direction == DeviceFacade.Direction.BOTTOM:
                _swipe(up, bottom)
        else:
            swipe_dir = ""
            if direction == DeviceFacade.Direction.TOP:
                swipe_dir = "up"
            elif direction == DeviceFacade.Direction.RIGHT:
                swipe_dir = "right"
            elif direction == DeviceFacade.Direction.LEFT:
                swipe_dir = "left"
            elif direction == DeviceFacade.Direction.BOTTOM:
                swipe_dir = "down"
            self.deviceV2.swipe_ext(swipe_dir, scale=scale)

    def swipe_points(self, sx, sy, ex, ey):
        if self.deviceV1 is not None:
            import uiautomator
            try:
                self.deviceV1.swipePoints([[sx, sy], [ex, ey]])
            except uiautomator.JsonRPCError as e:
                raise DeviceFacade.JsonRpcError(e)
        else:
            import uiautomator2
            try:
                self.deviceV2.swipe_points([[sx, sy], [ex, ey]], uniform(0.2, 0.6))
            except uiautomator2.JSONRPCError as e:
                raise DeviceFacade.JsonRpcError(e)

    def get_info(self):
        if self.deviceV1 is not None:
            return self.deviceV1.info
        else:
            return self.deviceV2.info

    def is_keyboard_open(self):
        cmd = f"adb {'' if self.device_id is None else ('-s '+ self.device_id)} shell dumpsys input_method"

        cmd_res = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, shell=True, encoding="utf8")
        data = cmd_res.stdout.strip()
        flag = search("mInputShown=(true|false)", data)
        return True if flag.group(1) == "true" else False

    def close_keyboard(self):
        print("Closing keyboard...")
        if self.is_keyboard_open():
            print("Keyboard is open, closing it by pressing back")
            self.back()
            print("Verifying again that keyboard is closed")
            if self.is_keyboard_open():
                print(COLOR_FAIL + "Keyboard is open and couldn't be closed for some reason" + COLOR_ENDC)
            else:
                print("The device keyboard is closed now.")

            return

        print("The device keyboard is already closed.")

    def _get_screen_size(self):
        if self.width is not None and self.height is not None:
            return self.width, self.height

        if self.deviceV1 is not None:
            self.width = self.deviceV1.info['displayWidth']
            self.height = self.deviceV1.info['displayHeight']
        else:
            self.width = self.deviceV2.info['displayWidth']
            self.height = self.deviceV2.info['displayHeight']

        return self.width, self.height

    class View:
        deviceV1 = None  # uiautomator
        viewV1 = None  # uiautomator
        deviceV2 = None  # uiautomator2
        viewV2 = None  # uiautomator2

        def __init__(self, is_old, view, device):
            if is_old:
                self.viewV1 = view
                self.deviceV1 = device
            else:
                self.viewV2 = view
                self.deviceV2 = device

        def __iter__(self):
            children = []
            if self.viewV1 is not None:
                import uiautomator
                try:
                    for item in self.viewV1:
                        children.append(DeviceFacade.View(is_old=True, view=item, device=self.deviceV1))
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    for item in self.viewV2:
                        children.append(DeviceFacade.View(is_old=False, view=item, device=self.deviceV2))
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            return iter(children)

        def child(self, *args, **kwargs):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    view = self.viewV1.child(*args, **kwargs)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
            else:
                import uiautomator2
                try:
                    view = self.viewV2.child(*args, **kwargs)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

        def right(self, *args, **kwargs):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    view = self.viewV1.right(*args, **kwargs)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
            else:
                import uiautomator2
                try:
                    view = self.viewV2.right(*args, **kwargs)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

        def left(self, *args, **kwargs):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    view = self.viewV1.left(*args, **kwargs)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
            else:
                import uiautomator2
                try:
                    view = self.viewV2.left(*args, **kwargs)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

        def up(self, *args, **kwargs):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    view = self.viewV1.up(*args, **kwargs)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
            else:
                import uiautomator2
                try:
                    view = self.viewV2.up(*args, **kwargs)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

        def down(self, *args, **kwargs):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    view = self.viewV1.down(*args, **kwargs)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=True, view=view, device=self.deviceV1)
            else:
                import uiautomator2
                try:
                    view = self.viewV2.down(*args, **kwargs)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return DeviceFacade.View(is_old=False, view=view, device=self.deviceV2)

        def click(self, mode=None):
            mode = DeviceFacade.Place.WHOLE if mode is None else mode
            if mode == DeviceFacade.Place.WHOLE:
                x_offset = uniform(0.15, 0.85)
                y_offset = uniform(0.15, 0.85)

            elif mode == DeviceFacade.Place.LEFT:
                x_offset = uniform(0.15, 0.4)
                y_offset = uniform(0.15, 0.85)

            elif mode == DeviceFacade.Place.CENTER:
                x_offset = uniform(0.4, 0.6)
                y_offset = uniform(0.15, 0.85)

            elif mode == DeviceFacade.Place.RIGHT:
                x_offset = uniform(0.6, 0.85)
                y_offset = uniform(0.15, 0.85)

            else:
                x_offset = 0.5
                y_offset = 0.5

            if self.viewV1 is not None:
                import uiautomator
                try:
                    self.viewV1.click.wait()
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    self.viewV2.click(UI_TIMEOUT_LONG, offset=(x_offset, y_offset))
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def double_click(self, padding=0.3):
            """
            Double click randomly in the selected view using padding
            padding: % of how far from the borders we want the double click to happen.
            """

            if self.viewV1 is not None:
                self._double_click_v1()
            else:
                self._double_click_v2(padding)

        def scroll(self, direction):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    if direction == DeviceFacade.Direction.TOP:
                        self.viewV1.scroll.toBeginning(max_swipes=1)
                    else:
                        self.viewV1.scroll.toEnd(max_swipes=1)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    if direction == DeviceFacade.Direction.TOP:
                        self.viewV2.scroll.toBeginning(max_swipes=1)
                    else:
                        self.viewV2.scroll.toEnd(max_swipes=1)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def swipe(self, direction):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    if direction == DeviceFacade.Direction.TOP:
                        self.viewV1.fling.toBeginning(max_swipes=5)
                    else:
                        self.viewV1.fling.toEnd(max_swipes=5)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    if direction == DeviceFacade.Direction.TOP:
                        self.viewV2.fling.toBeginning(max_swipes=5)
                    else:
                        self.viewV2.fling.toEnd(max_swipes=5)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def exists(self, quick=False):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    return self.viewV1.exists
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    return self.viewV2.exists(UI_TIMEOUT_SHORT if quick else UI_TIMEOUT_LONG)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def wait(self):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    self.deviceV1.wait.idle()
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
                return True
            else:
                import uiautomator2
                try:
                    return self.viewV2.wait(timeout=UI_TIMEOUT_LONG)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def get_bounds(self):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    return self.viewV1.bounds
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    return self.viewV2.info['bounds']
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def get_text(self, retry=True):
            max_attempts = 1 if not retry else 3
            attempts = 0

            if self.viewV1 is not None:
                import uiautomator
                while attempts < max_attempts:
                    attempts += 1
                    try:
                        text = self.viewV1.text
                        if text is None:
                            if attempts < max_attempts:
                                print(COLOR_REPORT + "Could not get text. Waiting 2 seconds and trying again..." + COLOR_ENDC)
                                sleep(2)  # wait 2 seconds and retry
                                continue
                        else:
                            return text
                    except uiautomator.JsonRPCError as e:
                        raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                while attempts < max_attempts:
                    attempts += 1
                    try:
                        text = self.viewV2.info['text']
                        if text is None:
                            if attempts < max_attempts:
                                print(COLOR_REPORT + "Could not get text. "
                                                     "Waiting 2 seconds and trying again..." + COLOR_ENDC)
                                sleep(2)  # wait 2 seconds and retry
                                continue
                        else:
                            return text
                    except uiautomator2.JSONRPCError as e:
                        raise DeviceFacade.JsonRpcError(e)

            print(COLOR_FAIL + f"Attempted to get text {attempts} times. You may have a slow network or are "
                               f"experiencing another problem." + COLOR_ENDC)
            return ""

        def get_selected(self) -> bool:
            if self.viewV1 is not None:
                import uiautomator
                try:
                    self.viewV1.info["selected"]
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    return self.viewV2.info["selected"]
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def set_text(self, text):
            if self.viewV1 is not None:
                import uiautomator
                try:
                    self.viewV1.set_text(text)
                except uiautomator.JsonRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)
            else:
                import uiautomator2
                try:
                    self.viewV2.set_text(text)
                except uiautomator2.JSONRPCError as e:
                    raise DeviceFacade.JsonRpcError(e)

        def _double_click_v1(self):
            import uiautomator
            config = self.deviceV1.server.jsonrpc.getConfigurator()
            config['actionAcknowledgmentTimeout'] = 40
            self.deviceV1.server.jsonrpc.setConfigurator(config)
            try:
                self.viewV1.click()
                self.viewV1.click()
            except uiautomator.JsonRPCError as e:
                raise DeviceFacade.JsonRpcError(e)
            config['actionAcknowledgmentTimeout'] = 3000
            self.deviceV1.server.jsonrpc.setConfigurator(config)

        def _double_click_v2(self, padding):
            import uiautomator2
            visible_bounds = self.get_bounds()
            horizontal_len = visible_bounds["right"] - visible_bounds["left"]
            vertical_len = visible_bounds["bottom"] - visible_bounds["top"]
            horizintal_padding = int(padding * horizontal_len)
            vertical_padding = int(padding * vertical_len)
            random_x = int(
                uniform(
                    visible_bounds["left"] + horizintal_padding,
                    visible_bounds["right"] - horizintal_padding,
                )
            )
            random_y = int(
                uniform(
                    visible_bounds["top"] + vertical_padding,
                    visible_bounds["bottom"] - vertical_padding,
                )
            )
            time_between_clicks = uniform(0.050, 0.200)
            try:
                self.deviceV2.double_click(random_x, random_y, duration=time_between_clicks)
            except uiautomator2.JSONRPCError as e:
                raise DeviceFacade.JsonRpcError(e)

    @unique
    class Direction(Enum):
        TOP = 0
        BOTTOM = 1
        RIGHT = 2
        LEFT = 3

    @unique
    class Place(Enum):
        # TODO: add more places
        RIGHT = 0
        WHOLE = 1
        CENTER = 2
        BOTTOM = 3
        LEFT = 4

    class JsonRpcError(Exception):
        pass
