from random import shuffle

from insomniac.actions_types import LikeAction, FollowAction, GetProfileAction, StoryWatchAction
from insomniac.device_facade import DeviceFacade
from insomniac.navigation import switch_to_english, search_for, LanguageChangedException
from insomniac.scroll_end_detector import ScrollEndDetector
from insomniac.sleeper import sleeper
from insomniac.softban_indicator import softban_indicator
from insomniac.utils import *
from insomniac.views import ActionBarView

FOLLOWERS_BUTTON_ID_REGEX = '{0}:id/row_profile_header_followers_container' \
                            '|{1}:id/row_profile_header_container_followers'
TEXTVIEW_OR_BUTTON_REGEX = 'android.widget.TextView|android.widget.Button'
FOLLOW_REGEX = 'Follow|Follow Back'
UNFOLLOW_REGEX = 'Following|Requested'
SHOP_REGEX = 'Add Shop|View Shop'
FOLLOWING_BUTTON_ID_REGEX = '{0}:id/row_profile_header_following_container' \
                            '|{1}:id/row_profile_header_container_following'
USER_AVATAR_VIEW_ID = '{0}:id/circular_image|^$'

liked_count = 0
is_followed = False


class InteractionStrategy(object):
    def __init__(self, do_like=False, do_follow=False, do_story_watch=False,
                 likes_count=2, like_percentage=100, follow_percentage=0, stories_count=2):
        self.do_like = do_like
        self.do_follow = do_follow
        self.do_story_watch = do_story_watch
        self.likes_count = likes_count
        self.follow_percentage = follow_percentage
        self.like_percentage = like_percentage
        self.stories_count = stories_count


def scroll_to_bottom(device):
    print("Scroll to bottom")

    def is_end_reached():
        see_all_button = device.find(resourceId=f'{device.app_id}:id/see_all_button',
                                     className='android.widget.TextView')
        return see_all_button.exists()

    list_view = device.find(resourceId='android:id/list',
                            className='android.widget.ListView')
    while not is_end_reached():
        list_view.swipe(DeviceFacade.Direction.BOTTOM)

    print("Scroll back to the first follower")

    def is_at_least_one_follower():
        follower = device.find(resourceId=f'{device.app_id}:id/follow_list_container',
                               className='android.widget.LinearLayout')
        return follower.exists()

    while not is_at_least_one_follower():
        list_view.scroll(DeviceFacade.Direction.TOP)


def is_private_account(device):
    recycler_view = device.find(resourceId='android:id/list')
    return not recycler_view.exists()


def open_user(device, username, refresh=False, on_action=None):
    return _open_user(device, username, False, False, refresh, on_action)


def open_user_followers(device, username, refresh=False, on_action=None):
    return _open_user(device, username, True, False, refresh, on_action)


def open_user_followings(device, username, refresh=False, on_action=None):
    return _open_user(device, username, False, True, refresh, on_action)


def iterate_over_followers(device, is_myself, iteration_callback,
                           iteration_callback_pre_conditions, iterate_without_sleep=False):
    # Wait until list is rendered
    device.find(resourceId=f'{device.app_id}:id/follow_list_container',
                className='android.widget.LinearLayout').wait()

    def scrolled_to_top():
        row_search = device.find(resourceId=f'{device.app_id}:id/row_search_edit_text',
                                 className='android.widget.EditText')
        return row_search.exists()

    prev_screen_iterated_followers = []
    scroll_end_detector = ScrollEndDetector()
    while True:
        print("Iterate over visible followers")
        if not iterate_without_sleep:
            sleeper.random_sleep()

        screen_iterated_followers = []
        screen_skipped_followers_count = 0
        scroll_end_detector.notify_new_page()

        try:
            for item in device.find(resourceId=f'{device.app_id}:id/follow_list_container',
                                    className='android.widget.LinearLayout'):
                user_info_view = item.child(index=1)
                user_name_view = user_info_view.child(index=0).child()
                if not user_name_view.exists(quick=True):
                    print(COLOR_OKGREEN + "Next item not found: probably reached end of the screen." + COLOR_ENDC)
                    break

                username = user_name_view.get_text()
                screen_iterated_followers.append(username)
                scroll_end_detector.notify_username_iterated(username)

                if not iteration_callback_pre_conditions(username, user_name_view):
                    screen_skipped_followers_count += 1
                    continue

                to_continue = iteration_callback(username, user_name_view)
                if not to_continue:
                    print(COLOR_OKBLUE + "Stopping followers iteration" + COLOR_ENDC)
                    return

        except IndexError:
            print(COLOR_FAIL + "Cannot get next item: probably reached end of the screen." + COLOR_ENDC)

        if is_myself and scrolled_to_top():
            print(COLOR_OKGREEN + "Scrolled to top, finish." + COLOR_ENDC)
            return
        elif len(screen_iterated_followers) > 0:
            load_more_button = device.find(resourceId=f'{device.app_id}:id/row_load_more_button')
            load_more_button_exists = load_more_button.exists(quick=True)

            if scroll_end_detector.is_the_end():
                return

            need_swipe = screen_skipped_followers_count == len(screen_iterated_followers)
            list_view = device.find(resourceId='android:id/list',
                                    className='android.widget.ListView')
            if not list_view.exists():
                print(COLOR_FAIL + "Cannot find the list of followers. Trying to press back again." + COLOR_ENDC)
                device.back()
                list_view = device.find(resourceId='android:id/list',
                                        className='android.widget.ListView')

            if is_myself:
                print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
                list_view.scroll(DeviceFacade.Direction.TOP)
            else:
                pressed_retry = False
                if load_more_button_exists:
                    retry_button = load_more_button.child(className='android.widget.ImageView')
                    if retry_button.exists():
                        print("Press \"Load\" button")
                        retry_button.click()
                        sleeper.random_sleep()
                        pressed_retry = True

                if need_swipe and not pressed_retry:
                    print(COLOR_OKGREEN + "All followers skipped, let's do a swipe" + COLOR_ENDC)
                    list_view.swipe(DeviceFacade.Direction.BOTTOM)
                else:
                    print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
                    list_view.scroll(DeviceFacade.Direction.BOTTOM)

            prev_screen_iterated_followers.clear()
            prev_screen_iterated_followers += screen_iterated_followers
        else:
            print(COLOR_OKGREEN + "No followers were iterated, finish." + COLOR_ENDC)
            return


def iterate_over_likers(device, iteration_callback, iteration_callback_pre_conditions):
    likes_list_view = device.find(resourceId='android:id/list',
                                  className='android.widget.ListView')
    prev_screen_iterated_likers = []
    while True:
        print("Iterate over visible likers.")
        screen_iterated_likers = []

        try:
            for item in device.find(resourceId=f'{device.app_id}:id/row_user_container_base',
                                    className='android.widget.LinearLayout'):
                user_name_view = item.child(resourceId=f'{device.app_id}:id/row_user_primary_name',
                                            className='android.widget.TextView')
                if not user_name_view.exists(quick=True):
                    print(COLOR_OKGREEN + "Next item not found: probably reached end of the screen." + COLOR_ENDC)
                    break

                username = user_name_view.get_text()
                screen_iterated_likers.append(username)

                if not iteration_callback_pre_conditions(username, user_name_view):
                    continue

                to_continue = iteration_callback(username, user_name_view)
                if not to_continue:
                    print(COLOR_OKBLUE + "Stopping hashtag-likers iteration" + COLOR_ENDC)
                    print(f"Going back")
                    device.back()
                    return False
        except IndexError:
            print(COLOR_FAIL + "Cannot get next item: probably reached end of the screen." + COLOR_ENDC)

        if screen_iterated_likers == prev_screen_iterated_likers:
            print(COLOR_OKGREEN + "Iterated exactly the same likers twice, finish." + COLOR_ENDC)
            print(f"Going back")
            device.back()
            break

        prev_screen_iterated_likers.clear()
        prev_screen_iterated_likers += screen_iterated_likers

        print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
        likes_list_view.scroll(DeviceFacade.Direction.BOTTOM)

    return True


def interact_with_user(device,
                       user_source,
                       username,
                       my_username,
                       interaction_strategy: InteractionStrategy,
                       on_action) -> (bool, bool):
    """
    :return: (whether some photos was liked, whether @username was followed during the interaction)
    """
    global liked_count, is_followed
    liked_count = 0
    is_followed = False
    is_watched = False

    if username == my_username:
        print("It's you, skip.")
        return liked_count == interaction_strategy.likes_count, is_followed, is_watched

    sleeper.random_sleep()

    if interaction_strategy.do_story_watch:
        is_watched = _watch_stories(device, username, interaction_strategy.stories_count, on_action)

    coordinator_layout = device.find(resourceId=f'{device.app_id}:id/coordinator_root_layout')
    if coordinator_layout.exists():
        print("Scroll down to see more photos.")
        coordinator_layout.scroll(DeviceFacade.Direction.BOTTOM)

    if interaction_strategy.do_like:
        number_of_rows_to_use = min((interaction_strategy.likes_count * 2) // 3 + 1, 4)
        photos_indices = list(range(0, number_of_rows_to_use * 3))
        shuffle(photos_indices)
        photos_indices = photos_indices[:interaction_strategy.likes_count]
        photos_indices = sorted(photos_indices)

        def on_like():
            global liked_count
            liked_count += 1
            print(COLOR_OKGREEN + "@{} - photo been liked.".format(username) + COLOR_ENDC)
            on_action(LikeAction(source=user_source, user=username))

        for i in range(0, interaction_strategy.likes_count):
            photo_index = photos_indices[i]
            row = photo_index // 3
            column = photo_index - row * 3

            sleeper.random_sleep()
            print("Open and like photo #" + str(i + 1) + " (" + str(row + 1) + " row, " + str(column + 1) + " column)")
            if not _open_photo_and_like(device, row, column, interaction_strategy.like_percentage, on_like):
                print(COLOR_OKGREEN + "Less than " + str(number_of_rows_to_use * 3) + " photos." + COLOR_ENDC)
                break

    if interaction_strategy.do_follow:
        is_followed = _follow(device, username, interaction_strategy.follow_percentage)
        if is_followed:
            print(COLOR_OKGREEN + "Following @{}.".format(username) + COLOR_ENDC)
            on_action(FollowAction(source=user_source, user=username))

    return liked_count > 0, is_followed, is_watched


def _open_photo_and_like(device, row, column, like_percentage, on_like):
    def open_photo():
        # recycler_view has a className 'androidx.recyclerview.widget.RecyclerView' on modern Android versions and
        # 'android.view.View' on Android 5.0.1 and probably earlier versions
        recycler_view = device.find(resourceId='android:id/list')
        row_view = recycler_view.child(index=row + 1)
        if not row_view.exists():
            return False
        item_view = row_view.child(index=column)
        if not item_view.exists():
            return False
        item_view.click()
        return True

    if not open_photo():
        return False

    sleeper.random_sleep()

    to_like = True
    like_chance = randint(1, 100)
    if like_chance > like_percentage:
        print("Not going to like image due to like-percentage hit")
        to_like = False

    if to_like:
        print("Double click!")
        photo_view = device.find(resourceId=f'{device.app_id}:id/layout_container_main',
                                 className='android.widget.FrameLayout')
        photo_view.double_click()
        sleeper.random_sleep()

        # If double click didn't work, set like by icon click
        try:
            # Click only button which is under the action bar and above the tab bar.
            # It fixes bugs with accidental back / home clicks.
            for like_button in device.find(resourceId=f'{device.app_id}:id/row_feed_button_like',
                                           className='android.widget.ImageView',
                                           selected=False):
                if ActionBarView.is_in_interaction_rect(like_button):
                    print("Double click didn't work, click on icon.")
                    like_button.click()
                    sleeper.random_sleep()
                    break
        except DeviceFacade.JsonRpcError:
            print("Double click worked successfully.")

        softban_indicator.detect_action_blocked_dialog(device)
        on_like()

    print("Back to profile")
    device.back()
    return True


def _follow(device, username, follow_percentage):
    follow_chance = randint(1, 100)
    if follow_chance > follow_percentage:
        return False

    print("Following...")
    coordinator_layout = device.find(resourceId=f'{device.app_id}:id/coordinator_root_layout')
    if coordinator_layout.exists():
        coordinator_layout.scroll(DeviceFacade.Direction.TOP)

    sleeper.random_sleep()

    profile_header_main_layout = device.find(resourceId=f"{device.app_id}:id/profile_header_fixed_list",
                                             className='android.widget.LinearLayout')

    shop_button = profile_header_main_layout.child(className='android.widget.Button',
                                                   clickable=True,
                                                   textMatches=SHOP_REGEX)

    if shop_button.exists(quick=True):
        follow_button = profile_header_main_layout.child(className='android.widget.Button',
                                                         clickable=True,
                                                         textMatches=FOLLOW_REGEX)
        if not follow_button.exists():
            print(COLOR_FAIL + "Look like a shop profile without an option to follow, continue." + COLOR_ENDC)
            return False
    else:
        profile_header_actions_layout = device.find(resourceId=f'{device.app_id}:id/profile_header_actions_top_row',
                                                    className='android.widget.LinearLayout')
        if not profile_header_actions_layout.exists():
            print(COLOR_FAIL + "Cannot find profile actions." + COLOR_ENDC)
            return False

        follow_button = profile_header_actions_layout.child(classNameMatches=TEXTVIEW_OR_BUTTON_REGEX,
                                                            clickable=True,
                                                            textMatches=FOLLOW_REGEX)

        if not follow_button.exists():
            unfollow_button = profile_header_actions_layout.child(classNameMatches=TEXTVIEW_OR_BUTTON_REGEX,
                                                                  clickable=True,
                                                                  textMatches=UNFOLLOW_REGEX)
            if unfollow_button.exists():
                print(COLOR_OKGREEN + "You already follow @" + username + "." + COLOR_ENDC)
                return False
            else:
                print(COLOR_FAIL + "Cannot find neither Follow button, nor Unfollow button. Maybe not "
                                   "English language is set?" + COLOR_ENDC)
                save_crash(device)
                switch_to_english(device)
                return False

    follow_button.click()
    softban_indicator.detect_action_blocked_dialog(device)
    print(COLOR_OKGREEN + "Followed @" + username + COLOR_ENDC)
    sleeper.random_sleep()
    return True


def do_have_story(device):
    return device.find(resourceId=f"{device.app_id}:id/reel_ring",
                       className="android.view.View").exists(quick=True)


def is_already_followed(device):
    # Using main layout in order to support shop pages
    profile_header_main_layout = device.find(resourceId=f"{device.app_id}:id/profile_header_fixed_list",
                                             className='android.widget.LinearLayout')
    unfollow_button = profile_header_main_layout.child(classNameMatches=TEXTVIEW_OR_BUTTON_REGEX,
                                                       clickable=True,
                                                       textMatches=UNFOLLOW_REGEX)
    return unfollow_button.exists(quick=True)


def _watch_stories(device, username, stories_value, on_action):
    if stories_value == 0:
        return False

    if do_have_story(device):
        profile_picture = device.find(
            resourceId=f"{device.app_id}:id/row_profile_header_imageview",
            className="android.widget.ImageView"
        )

        if profile_picture.exists():
            print(COLOR_OKGREEN + f"Watching @" + username + f" stories, at most {stories_value}" + COLOR_ENDC)

            profile_picture.click()  # Open the first story
            on_action(StoryWatchAction(user=username))
            sleeper.random_sleep()

            for i in range(1, stories_value):
                if _skip_story(device):
                    print("Watching next story...")
                    sleeper.random_sleep()
                else:
                    print(COLOR_OKGREEN + "Watched all stories" + COLOR_ENDC)
                    break

            if not _get_action_bar(device).exists():
                print("Back to profile")
                device.back()
            return True
    return False


def _skip_story(device):
    if _is_story_opened(device):
        device.screen_click(DeviceFacade.Place.RIGHT)
        return True
    else:
        return False


def _is_story_opened(device):
    reel_viewer = device.find(resourceId=f"{device.app_id}:id/reel_viewer_root",
                              className="android.widget.FrameLayout")
    return reel_viewer.exists()


def _open_user(device, username, open_followers=False, open_followings=False, refresh=False, on_action=None):
    if refresh:
        print("Refreshing profile status...")
        coordinator_layout = device.find(resourceId=f'{device.app_id}:id/coordinator_root_layout')
        if coordinator_layout.exists():
            coordinator_layout.scroll(DeviceFacade.Direction.TOP)

    if username is None:
        if open_followers:
            print("Open your followers")
            followers_button = device.find(resourceIdMatches=FOLLOWERS_BUTTON_ID_REGEX.format(device.app_id, device.app_id))
            followers_button.click()

        if open_followings:
            print("Open your followings")
            followings_button = device.find(resourceIdMatches=FOLLOWING_BUTTON_ID_REGEX.format(device.app_id, device.app_id))
            followings_button.click()
    else:
        if not search_for(device, username=username, on_action=on_action):
            return False

        sleeper.random_sleep()

        is_profile_empty = softban_indicator.detect_empty_profile(device)
        if is_profile_empty:
            return False

        if open_followers:
            print("Open @" + username + " followers")
            followers_button = device.find(resourceIdMatches=FOLLOWERS_BUTTON_ID_REGEX.format(device.app_id, device.app_id))
            followers_button.click()

        if open_followings:
            print("Open @" + username + " followings")
            followings_button = device.find(resourceIdMatches=FOLLOWING_BUTTON_ID_REGEX.format(device.app_id, device.app_id))
            followings_button.click()

    return True


def iterate_over_followings(device, iteration_callback, iteration_callback_pre_conditions):
    # Wait until list is rendered
    device.find(resourceId=f'{device.app_id}:id/follow_list_container',
                className='android.widget.LinearLayout').wait()

    while True:
        print("Iterate over visible followings")
        sleeper.random_sleep()
        screen_iterated_followings = 0

        for item in device.find(resourceId=f'{device.app_id}:id/follow_list_container',
                                className='android.widget.LinearLayout'):
            user_info_view = item.child(index=1)
            user_name_view = user_info_view.child(index=0).child()
            if not user_name_view.exists(quick=True):
                print(COLOR_OKGREEN + "Next item not found: probably reached end of the screen." + COLOR_ENDC)
                break

            username = user_name_view.get_text()
            screen_iterated_followings += 1

            if not iteration_callback_pre_conditions(username, user_name_view):
                continue

            to_continue = iteration_callback(username, user_name_view)
            if to_continue:
                sleeper.random_sleep()
            else:
                print(COLOR_OKBLUE + "Stopping iteration over followings" + COLOR_ENDC)
                return

        if screen_iterated_followings > 0:
            print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
            list_view = device.find(resourceId='android:id/list',
                                    className='android.widget.ListView')
            list_view.scroll(DeviceFacade.Direction.BOTTOM)
        else:
            print(COLOR_OKGREEN + "No followings were iterated, finish." + COLOR_ENDC)
            return


def sort_followings_by_date(device):
    print("Sort followings by date: from oldest to newest.")
    sort_button = device.find(resourceId=f'{device.app_id}:id/sorting_entry_row_icon',
                              className='android.widget.ImageView')
    if not sort_button.exists():
        print(COLOR_FAIL + "Cannot find button to sort followings. Continue without sorting." + COLOR_ENDC)
        return
    sort_button.click()

    sort_options_recycler_view = device.find(
        resourceId=f'{device.app_id}:id/follow_list_sorting_options_recycler_view')
    if not sort_options_recycler_view.exists():
        print(COLOR_FAIL + "Cannot find options to sort followings. Continue without sorting." + COLOR_ENDC)
        return

    sort_options_recycler_view.child(index=2).click()


def do_unfollow(device, username, my_username, check_if_is_follower, on_action):
    """
    :return: whether unfollow was successful
    """
    username_view = device.find(resourceId=f'{device.app_id}:id/follow_list_username',
                                className='android.widget.TextView',
                                text=username)
    if not username_view.exists():
        print(COLOR_FAIL + "Cannot find @" + username + ", skip." + COLOR_ENDC)
        return False
    username_view.click()
    on_action(GetProfileAction(user=username))
    sleeper.random_sleep()
    if_profile_empty = softban_indicator.detect_empty_profile(device)

    if if_profile_empty:
        print("Back to the followings list.")
        device.back()
        return False

    if check_if_is_follower and _check_is_follower(device, username, my_username):
        print("Skip @" + username + ". This user is following you.")
        print("Back to the followings list.")
        device.back()
        return False

    unfollow_button = device.find(classNameMatches=TEXTVIEW_OR_BUTTON_REGEX,
                                  clickable=True,
                                  text='Following')
    if not unfollow_button.exists():
        print(COLOR_FAIL + "Cannot find Following button. Maybe not English language is set?" + COLOR_ENDC)
        save_crash(device)
        switch_to_english(device)
        raise LanguageChangedException()
    unfollow_button.click()

    confirm_unfollow_button = device.find(resourceId=f'{device.app_id}:id/follow_sheet_unfollow_row',
                                          className='android.widget.TextView')
    if not confirm_unfollow_button.exists():
        print(COLOR_FAIL + "Cannot confirm unfollow." + COLOR_ENDC)
        save_crash(device)
        device.back()
        return False
    confirm_unfollow_button.click()

    sleeper.random_sleep()
    _close_confirm_dialog_if_shown(device)
    softban_indicator.detect_action_blocked_dialog(device)

    print("Back to the followings list.")
    device.back()
    return True


def open_likers(device):
    likes_view = device.find(resourceId=f'{device.app_id}:id/row_feed_textview_likes',
                             className='android.widget.TextView')
    if likes_view.exists(quick=True) and ActionBarView.is_in_interaction_rect(likes_view):
        print("Opening post likers")
        sleeper.random_sleep()
        likes_view.click()
        return True
    else:
        return False


def _check_is_follower(device, username, my_username):
    print(COLOR_OKGREEN + "Check if @" + username + " is following you." + COLOR_ENDC)
    following_container = device.find(resourceIdMatches=FOLLOWING_BUTTON_ID_REGEX.format(device.app_id, device.app_id))
    following_container.click()

    sleeper.random_sleep()

    is_list_empty = softban_indicator.detect_empty_list(device)

    if is_list_empty:
        # By default, the profile will be considered as following if the profile list didnt loaded
        print("List seems to be empty, cant decide if you are followed by the profile or not (could be a soft-ban).")
        print("Back to the profile.")
        device.back()
        return True
    else:
        my_username_view = device.find(resourceId=f'{device.app_id}:id/follow_list_username',
                                       className='android.widget.TextView',
                                       text=my_username)
        result = my_username_view.exists()
        print("Back to the profile.")
        device.back()
        return result


def _close_confirm_dialog_if_shown(device):
    dialog_root_view = device.find(resourceId=f'{device.app_id}:id/dialog_root_view',
                                   className='android.widget.FrameLayout')
    if not dialog_root_view.exists():
        return

    # Avatar existence is the way to distinguish confirm dialog from block dialog
    user_avatar_view = device.find(resourceIdMatches=USER_AVATAR_VIEW_ID.format(device.app_id),
                                   className='android.widget.ImageView')
    if not user_avatar_view.exists():
        return

    print(COLOR_OKGREEN + "Dialog shown, confirm unfollowing." + COLOR_ENDC)
    sleeper.random_sleep()
    unfollow_button = dialog_root_view.child(resourceId=f'{device.app_id}:id/primary_button',
                                             className='android.widget.TextView')
    unfollow_button.click()


def _get_action_bar(device):
    tab_bar = device.find(
        resourceIdMatches=case_insensitive_re(
            f"{device.app_id}:id/action_bar_container"
        ),
        className="android.widget.FrameLayout",
    )
    return tab_bar


def case_insensitive_re(str_list):
    if isinstance(str_list, str):
        strings = str_list
    else:
        strings = "|".join(str_list)
    re_str = f"(?i)({strings})"
    return re_str
