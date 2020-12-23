import random

from insomniac.action_runners import *
from insomniac.safely_runner import run_safely
from insomniac.utils import *


class InteractBySourceActionRunner(CoreActionsRunner):
    ACTION_ID = "interact"
    ACTION_ARGS = {
        "likes_count": {
            "help": "number of likes for each interacted user, 2 by default. "
                    "It can be a number (e.g. 2) or a range (e.g. 2-4)",
            'metavar': '2-4',
            "default": '2'
        },
        "like_percentage": {
            "help": "likes given percentage of interacted users, 100 by default",
            "metavar": '50',
            "default": '100'
        },
        "follow_percentage": {
            "help": "follow given percentage of interacted users, 0 by default",
            "metavar": '50',
            "default": '0'
        },
        "interact": {
            "nargs": '+',
            "help": 'list of hashtags and usernames. Usernames should start with \"@\" symbol. '
                    'You can specify the way of interaction after a \"-\" sign: @username-followers, '
                    '@username-following, hashtag-top-likers, hashtag-recent-likers',
            "default": [],
            "metavar": ('hashtag-top-likers', '@username-followers')
        },
        "interaction_users_amount": {
            "help": 'add this argument to select an amount of users from the interact-list '
                    '(users are randomized). It can be a number (e.g. 4) or a range (e.g. 3-8)',
            'metavar': '3-8'
        },
        "stories_count": {
            "help": 'number of stories to watch for each user, disabled by default. '
                    'It can be a number (e.g. 2) or a range (e.g. 2-4)',
            'metavar': '3-8'
        },
    }

    likes_count = '2'
    follow_percentage = 0
    like_percentage = 100
    interact = []
    stories_count = '0'

    def is_action_selected(self, args):
        return args.interact is not None and len(args.interact) > 0

    def set_params(self, args):
        if args.likes_count is not None:
            self.likes_count = args.likes_count

        if args.stories_count is not None:
            self.stories_count = args.stories_count

        if args.interact is not None:
            self.interact = args.interact.copy()
            self.interact = [source if source[0] == '@' else ('#' + source) for source in self.interact]

        if args.follow_percentage is not None:
            self.follow_percentage = int(args.follow_percentage)

        if args.like_percentage is not None:
            self.like_percentage = int(args.like_percentage)

        if args.interaction_users_amount is not None:
            if len(self.interact) > 0:
                users_amount = get_value(args.interaction_users_amount, "Interaction user amount {}", 100)

                if users_amount >= len(self.interact):
                    print("interaction-users-amount parameter is equal or higher then the users-interact list. "
                          "Choosing all list for interaction.")
                else:
                    amount_to_remove = len(self.interact) - users_amount
                    for i in range(0, amount_to_remove):
                        self.interact.remove(random.choice(self.interact))

    def run(self, device_wrapper, storage, session_state, on_action, is_limit_reached, is_passed_filters=None):
        from insomniac.action_runners.interact.action_handle_blogger import handle_blogger, extract_blogger_instructions
        from insomniac.action_runners.interact.action_handle_hashtag import handle_hashtag, extract_hashtag_instructions

        random.shuffle(self.interact)

        for source in self.interact:
            self.action_status = ActionStatus(ActionState.PRE_RUN)

            if source[0] == '@':
                is_myself = source[1:] == session_state.my_username
                print_timeless("")
                print(COLOR_BOLD + "Handle " + source + (is_myself and " (it\'s you)" or "") + COLOR_ENDC)
            elif source[0] == '#':
                print_timeless("")
                print(COLOR_BOLD + "Handle " + source + COLOR_ENDC)

            @run_safely(device_wrapper=device_wrapper)
            def job():
                self.action_status.set(ActionState.RUNNING)
                if source[0] == '@':
                    source_name, instructions = extract_blogger_instructions(source)
                    handle_blogger(device_wrapper.get(),
                                   source_name[1:],  # drop "@"
                                   instructions,
                                   session_state,
                                   self.likes_count,
                                   self.stories_count,
                                   self.follow_percentage,
                                   self.like_percentage,
                                   storage,
                                   on_action,
                                   is_limit_reached,
                                   is_passed_filters,
                                   self.action_status)
                elif source[0] == '#':
                    source_name, instructions = extract_hashtag_instructions(source)
                    handle_hashtag(device_wrapper.get(),
                                   source_name[1:],  # drop "#"
                                   instructions,
                                   session_state,
                                   self.likes_count,
                                   self.stories_count,
                                   self.follow_percentage,
                                   self.like_percentage,
                                   storage,
                                   on_action,
                                   is_limit_reached,
                                   is_passed_filters,
                                   self.action_status)

                self.action_status.set(ActionState.DONE)

            while not self.action_status.get() == ActionState.DONE:
                job()
                if self.action_status.get_limit() == ActionState.SOURCE_LIMIT_REACHED or \
                   self.action_status.get_limit() == ActionState.SESSION_LIMIT_REACHED:
                    break

            if self.action_status.get_limit() == ActionState.SOURCE_LIMIT_REACHED:
                continue

            if self.action_status.get_limit() == ActionState.SESSION_LIMIT_REACHED:
                break


class InteractByTargetsActionRunner(CoreActionsRunner):
    ACTION_ID = "interact_targets"
    ACTION_ARGS = {
        "interact_targets": {
            "help": "use this argument in order to interact with profiles from targets.txt",
            'metavar': 'True / False'
        },
        "likes_count": {
            "help": "number of likes for each interacted user, 2 by default. "
                    "It can be a number (e.g. 2) or a range (e.g. 2-4)",
            'metavar': '2-4',
            "default": '2'
        },
        "follow_percentage": {
            "help": "follow given percentage of interacted users, 0 by default",
            "metavar": '50',
            "default": '0'
        },
        "like_percentage": {
            "help": "likes given percentage of interacted users, 100 by default",
            "metavar": '50',
            "default": '100'
        },
        "stories_count": {
            "help": 'number of stories to watch for each user, disabled by default. '
                    'It can be a number (e.g. 2) or a range (e.g. 2-4)',
            'metavar': '3-8'
        }
    }

    likes_count = '2'
    follow_percentage = 0
    like_percentage = 100
    stories_count = '0'

    def is_action_selected(self, args):
        return args.interact_targets is not None

    def set_params(self, args):
        if args.likes_count is not None:
            self.likes_count = args.likes_count

        if args.stories_count is not None:
            self.stories_count = args.stories_count

        if args.follow_percentage is not None:
            self.follow_percentage = int(args.follow_percentage)

        if args.like_percentage is not None:
            self.like_percentage = int(args.like_percentage)

    def run(self, device_wrapper, storage, session_state, on_action, is_limit_reached, is_passed_filters=None):
        from insomniac.action_runners.interact.action_handle_target import handle_target

        target = storage.get_target()
        while target is not None:
            self.action_status = ActionStatus(ActionState.PRE_RUN)

            print_timeless("")
            print(COLOR_BOLD + "Handle @" + target + COLOR_ENDC)

            @run_safely(device_wrapper=device_wrapper)
            def job():
                self.action_status.set(ActionState.RUNNING)
                handle_target(device_wrapper.get(),
                              target,
                              session_state,
                              self.likes_count,
                              self.stories_count,
                              self.follow_percentage,
                              self.like_percentage,
                              storage,
                              on_action,
                              is_limit_reached,
                              is_passed_filters,
                              self.action_status)

                self.action_status.set(ActionState.DONE)

            while not self.action_status.get() == ActionState.DONE:
                job()
                if self.action_status.get_limit() == ActionState.SOURCE_LIMIT_REACHED or \
                        self.action_status.get_limit() == ActionState.SESSION_LIMIT_REACHED:
                    break

            if self.action_status.get_limit() == ActionState.SOURCE_LIMIT_REACHED:
                continue

            if self.action_status.get_limit() == ActionState.SESSION_LIMIT_REACHED:
                break

            target = storage.get_target()
