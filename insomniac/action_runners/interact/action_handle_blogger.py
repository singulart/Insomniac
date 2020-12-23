from functools import partial

from insomniac.action_runners.actions_runners_manager import ActionState
from insomniac.actions_impl import interact_with_user, InteractionStrategy, is_private_account
from insomniac.actions_providers import Provider
from insomniac.actions_types import LikeAction, FollowAction, InteractAction, GetProfileAction, StoryWatchAction, \
    BloggerInteractionType
from insomniac.limits import process_limits
from insomniac.report import print_short_report, print_interaction_types
from insomniac.sleeper import sleeper
from insomniac.softban_indicator import softban_indicator
from insomniac.storage import FollowingStatus
from insomniac.utils import *
from insomniac.views import TabBarView, ProfileView
from insomniac.counters import to_int


def extract_blogger_instructions(source):
    split_idx = source.find('-')
    if split_idx == -1:
        print("There is no special interaction-instructions for " + source + ". Working with " + source + " followers.")
        return source, BloggerInteractionType.FOLLOWERS

    selected_instruction = None
    source_profile_name = source[:split_idx]
    interaction_instructions_str = source[split_idx+1:]

    for blogger_instruction in BloggerInteractionType:
        if blogger_instruction.value == interaction_instructions_str:
            selected_instruction = blogger_instruction
            break

    if selected_instruction is None:
        print("Couldn't use interaction-instructions " + interaction_instructions_str +
              ". Working with " + source + " followers.")
        selected_instruction = BloggerInteractionType.FOLLOWERS

    return source_profile_name, selected_instruction


def handle_blogger(device,
                   username,
                   instructions,
                   session_state,
                   likes_count,
                   stories_count,
                   follow_percentage,
                   like_percentage,
                   storage,
                   on_action,
                   is_limit_reached,
                   is_passed_filters,
                   action_status):
    is_myself = username == session_state.my_username
    interaction = partial(interact_with_user,
                          device=device,
                          user_source=username,
                          my_username=session_state.my_username,
                          on_action=on_action)

    search_view = TabBarView(device).navigate_to_search()
    blogger_profile_view = search_view.navigate_to_username(username, on_action)

    if blogger_profile_view is None:
        return

    sleeper.random_sleep()
    is_profile_empty = softban_indicator.detect_empty_profile(device)

    if is_profile_empty:
        return

    followers_following_list_view = None
    if instructions == BloggerInteractionType.FOLLOWERS:
        followers_following_list_view = blogger_profile_view.navigate_to_followers()
    elif instructions == BloggerInteractionType.FOLLOWING:
        followers_following_list_view = blogger_profile_view.navigate_to_following()

    if is_myself:
        followers_following_list_view.scroll_to_bottom()
        followers_following_list_view.scroll_to_top()

    def pre_conditions(follower_name, follower_name_view):
        if storage.is_user_in_blacklist(follower_name):
            print("@" + follower_name + " is in blacklist. Skip.")
            return False
        elif storage.check_user_was_filtered(follower_name):
            print("@" + follower_name + ": already filtered in past. Skip.")
            return False
        elif not is_myself and storage.check_user_was_interacted(follower_name):
            print("@" + follower_name + ": already interacted. Skip.")
            return False
        elif is_myself and storage.check_user_was_interacted_recently(follower_name):
            print("@" + follower_name + ": already interacted in the last week. Skip.")
            return False
        elif is_passed_filters is not None:
            if not is_passed_filters(device, follower_name, reset=True, filters_tags=['BEFORE_PROFILE_CLICK']):
                storage.add_filtered_user(follower_name)
                return False

        return True

    def interact_with_follower(follower_name, follower_name_view):
        is_interact_limit_reached, interact_reached_source_limit, interact_reached_session_limit = \
            is_limit_reached(InteractAction(source=username, user=follower_name, succeed=True), session_state)

        if not process_limits(is_interact_limit_reached, interact_reached_session_limit,
                              interact_reached_source_limit, action_status, "Interaction"):
            return False

        is_get_profile_limit_reached, get_profile_reached_source_limit, get_profile_reached_session_limit = \
            is_limit_reached(GetProfileAction(user=follower_name), session_state)

        if not process_limits(is_get_profile_limit_reached, get_profile_reached_session_limit,
                              get_profile_reached_source_limit, action_status, "Get-Profile"):
            return False

        follower_name_view.click()
        on_action(GetProfileAction(user=follower_name))

        post_count = None
        followers_count = None
        following_count = None

        post_count_el = device.find(resourceId='com.instagram.android:id/row_profile_header_textview_post_count',
                                    className='android.widget.TextView')
        if post_count_el.exists():
            post_count = to_int(post_count_el.get_text())

        followers_count_el = device.find(resourceId='com.instagram.android:id/row_profile_header_textview_followers_count',
                                         className='android.widget.TextView')
        if followers_count_el.exists():
            followers_count = to_int(followers_count_el.get_text())

        following_count_el = device.find(resourceId='com.instagram.android:id/row_profile_header_textview_following_count',
                                         className='android.widget.TextView')
        if following_count_el.exists():
            following_count = to_int(following_count_el.get_text())

        print("@%s (PC=%s ERS=%s ING=%s): interact" % (follower_name, post_count, followers_count, following_count))

        with open('filters.json') as json_file:
            filterz = json.load(json_file)
        json_file.close()

        skip = False
        if post_count and post_count < filterz['min_posts']:
            skip = True
            print('Skip because of %s < min_posts' % post_count)
        if followers_count and followers_count < filterz['min_followers']:
            skip = True
            print('Skip because of %s < min_followers' % followers_count)
        if followers_count and followers_count > filterz['max_followers']:
            skip = True
            print('Skip because of %s > max_followers' % followers_count)
        if followers_count and following_count and followers_count / (following_count + 1) < filterz['min_potency_ratio']:
            skip = True
            print('Skip because of %s < min_potency_ratio' % (followers_count / (following_count + 1)))
        if followers_count and following_count and followers_count / (following_count + 1) > filterz['max_potency_ratio']:
            skip = True
            print('Skip because of %s > max_potency_ratio' % (followers_count / (following_count + 1)))
        if not filterz['follow_private_or_empty'] and is_private_account(device):
            skip = True
            print('Skipping private account')

        if skip:
            storage.add_filtered_user(follower_name)
            # Continue to next follower
            device.back()
            return True

        sleeper.random_sleep()
        is_profile_empty = softban_indicator.detect_empty_profile(device)

        if is_profile_empty:
            print("Back to followers list")
            device.back()
            return True

        follower_profile_view = ProfileView(device, follower_name == session_state.my_username)
        if is_passed_filters is not None:
            if not is_passed_filters(device, follower_name, reset=False):
                storage.add_filtered_user(follower_name)
                # Continue to next follower
                print("Back to profiles list")
                device.back()
                return True

        is_like_limit_reached, like_reached_source_limit, like_reached_session_limit = \
            is_limit_reached(LikeAction(source=username, user=follower_name), session_state)

        is_follow_limit_reached, follow_reached_source_limit, follow_reached_session_limit = \
            is_limit_reached(FollowAction(source=username, user=follower_name), session_state)

        is_watch_limit_reached, watch_reached_source_limit, watch_reached_session_limit = \
            is_limit_reached(StoryWatchAction(user=follower_name), session_state)

        is_private = follower_profile_view.is_private_account()
        if is_private:
            print("@" + follower_name + ": Private account - images wont be liked.")

        do_have_stories = follower_profile_view.is_story_available()
        if not do_have_stories:
            print("@" + follower_name + ": seems there are no stories to be watched.")

        is_likes_enabled = likes_count != '0'
        is_stories_enabled = stories_count != '0'
        is_follow_enabled = follow_percentage != 0

        likes_value = get_value(likes_count, "Likes count: {}", 2, max_count=12)
        stories_value = get_value(stories_count, "Stories to watch: {}", 1)

        can_like = not is_like_limit_reached and not is_private and likes_value > 0
        can_follow = (not is_follow_limit_reached) and storage.get_following_status(follower_name) == FollowingStatus.NONE and follow_percentage > 0
        can_watch = (not is_watch_limit_reached) and do_have_stories and stories_value > 0
        can_interact = can_like or can_follow or can_watch

        if not can_interact:
            print("@" + follower_name + ": Cant be interacted (due to limits / already followed). Skip.")
            storage.add_interacted_user(follower_name,
                                        followed=False,
                                        source=f"@{username}",
                                        interaction_type=instructions.value,
                                        provider=Provider.INTERACTION)
            on_action(InteractAction(source=username, user=follower_name, succeed=False))
        else:
            print_interaction_types(follower_name, can_like, can_follow, can_watch)
            interaction_strategy = InteractionStrategy(do_like=can_like,
                                                       do_follow=can_follow,
                                                       do_story_watch=can_watch,
                                                       likes_count=likes_value,
                                                       follow_percentage=follow_percentage,
                                                       like_percentage=like_percentage,
                                                       stories_count=stories_value)

            is_liked, is_followed, is_watch = interaction(username=follower_name, interaction_strategy=interaction_strategy)
            if is_liked or is_followed or is_watch:
                storage.add_interacted_user(follower_name,
                                            followed=is_followed,
                                            source=f"@{username}",
                                            interaction_type=instructions.value,
                                            provider=Provider.INTERACTION)
                on_action(InteractAction(source=username, user=follower_name, succeed=True))
                print_short_report(username, session_state)
            else:
                storage.add_interacted_user(follower_name,
                                            followed=False,
                                            source=f"@{username}",
                                            interaction_type=instructions.value,
                                            provider=Provider.INTERACTION)
                on_action(InteractAction(source=username, user=follower_name, succeed=False))

        can_continue = True

        if ((is_like_limit_reached and is_likes_enabled) or not is_likes_enabled) and \
           ((is_follow_limit_reached and is_follow_enabled) or not is_follow_enabled) and \
           ((is_watch_limit_reached and is_stories_enabled) or not is_stories_enabled):
            # If one of the limits reached for source-limit, move to next source
            if (like_reached_source_limit is not None and like_reached_session_limit is None) or \
               (follow_reached_source_limit is not None and follow_reached_session_limit is None):
                can_continue = False
                action_status.set_limit(ActionState.SOURCE_LIMIT_REACHED)

            # If all of the limits reached for session-limit, finish the session
            if ((like_reached_session_limit is not None and is_likes_enabled) or not is_likes_enabled) and \
               ((follow_reached_session_limit is not None and is_follow_enabled) or not is_follow_enabled):
                can_continue = False
                action_status.set_limit(ActionState.SESSION_LIMIT_REACHED)

        print("Back to profiles list")
        device.back()

        return can_continue

    followers_following_list_view.iterate_over_followers(is_myself, interact_with_follower, pre_conditions)
