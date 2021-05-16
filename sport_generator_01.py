# !/usr/bin/env python3

# libraries
import argparse
import json
from random import Random
import os
import requests
from enum import Enum
from typing import List, NamedTuple
from string import Template as Tmpl
from dataclasses import dataclass
from copy import deepcopy


# handling arguments
parser = argparse.ArgumentParser()
parser.add_argument("--match_data", default="data/livesport_matches/0Ao9H20P.json", type=str,
                    help="JSON file with match data")
parser.add_argument("--test", default=False, type=bool, help="Testing for errors in each match")


# --------------------------------------------------------------------------------------------------------------------
# General Classes

class Types:
    class Result(Enum):
        # always in home's team perspective
        WIN = 1
        DRAW = 0
        LOSS = 2

    class Team(Enum):
        HOME = 0
        AWAY = 1

    class Incident(Enum):
        GOAL = 0
        PENALTY_KICK = 1
        CARD = 2
        SUBSTITUTION = 3

    class Card(Enum):
        YELLOW = 0,
        RED_AUTO = 1,
        RED_INSTANT = 2

    class Goal(Enum):
        PENALTY = 0,
        ASSISTANCE = 1,
        SOLO_PLAY = 2,
        OWN_GOAL = 3

    class Message(Enum):
        GOAL = 0
        PENALTY_KICK_MISSED = 1
        CARD = 3
        SUBSTITUTION = 4
        RESULT = 5

    class MessageSubtype(Enum):
        WIN = 0,
        DRAW = 1,
        LOSS = 2
        RED_INSTANT = 3,
        RED_AUTO = 4,
        YELLOW = 5,
        ASSISTANCE = 6,
        PENALTY = 7,
        SOLO_PLAY = 8,
        OWN_GOAL = 9


@dataclass(frozen=True)
class Score:
    goals_home: int
    goals_away: int
    goals_sum: int
    goals_difference: int
    result: Types.Result

    @staticmethod
    def create(goals_home: int, goals_away: int):
        goals_sum = goals_home + goals_away
        goals_difference = abs(goals_home - goals_away)
        result: Types.Result = Score._init_result(goals_home=goals_home, goals_away=goals_away)
        return Score(goals_home=goals_home, goals_away=goals_away, goals_sum=goals_sum,
                     goals_difference=goals_difference, result=result)

    @staticmethod
    def _init_result(goals_home: int, goals_away: int) -> Types.Result:
        if goals_home > goals_away:
            return Types.Result.WIN
        elif goals_home == goals_away:
            return Types.Result.DRAW
        else:
            return Types.Result.LOSS

    def __str__(self):
        return f'{self.goals_home}:{self.goals_away}'


@dataclass(frozen=True)
class Venue:
    name: str
    town: str
    capacity: int
    attendance: int
    full_percentage: int

    @staticmethod
    def create(name: str, town: str, capacity: int, attendance: int):
        full_percentage = round((attendance / capacity) * 100)
        return Venue(name=name, town=town, capacity=capacity, attendance=attendance, full_percentage=full_percentage)

    '''
        def __str__(self):
        return f"--Venue-- Name: {self.name}, Town: {self.town}, Capacity: {self.capacity}, " \
            f"Attendance: {self.attendance}, Percantage of at.: {self.full_percentage}, " \
            f"Venue is full: {self.is_full()}, Venue is empty: {self.is_empty()}"
    '''


@dataclass(frozen=True)
class Country:
    id: int
    name: str

    @staticmethod
    def create(id_: int, name_: str):
        return Country(id=id_, name=name_)


@dataclass(frozen=True)
class Player:
    id: int
    full_name: str
    country: Country
    lineup_position_id: int
    number: int

    @staticmethod
    def create(id_: int, full_name: str, country: Country, lineup_position_id: int, number: int):
        return Player(id=id_, full_name=full_name, country=country,
                      lineup_position_id=lineup_position_id, number=number)

    def get_first_name(self):
        return self.full_name.split()[-1]

    def get_last_name(self):
        return self.full_name.split()[0]

    def __str__(self):
        return f"({self.full_name}, {self.number})"


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    country: Country
    type: Types.Team
    lineup: List[Player]

    @staticmethod
    def create(id_: int, name: str, country: Country, type_: Types.Team, lineup: List[Player]):
        return Team(id=id_, name=name, country=country, type=type_, lineup=lineup)

    def __str__(self):
        return f"--Team-- Id: {self.id}, Name: {self.name}, type: {self.type.name}"


@dataclass(frozen=True)
class Time:
    base: int
    added: int

    @staticmethod
    def create(time_base: int, time_added: int):
        return Time(base=time_base, added=time_added)

    def __str__(self):
        if self.added != 0:
            return f"{self.base} + {self.added}"
        else:
            return str(self.base)

    def __lt__(self, other):
        if self.base != other.base:
            return self.base < other.base
        else:
            return self.added < other.added


@dataclass(frozen=True)
class Incident:
    type: Types.Incident
    participant: Player
    team: Team
    time: Time

    def __lt__(self, other):
        return self.time < other.time

    def __str__(self):
        return f"-> {self.type.name} ---  time: {self.time}, \
          participant: {self.participant.full_name}, team: {self.team.name}"


class Incidents:
    @dataclass(frozen=True)
    class Goal(Incident):
        current_score: Score
        assistance: Player
        goal_type: Types.Goal

        @staticmethod
        def create(participant: Player, team: Team, time: Time, current_score: Score,
                   assistance: Player, goal_type: Types.Goal):
            return Incidents.Goal(type=Types.Incident.GOAL, participant=participant, team=team, time=time,
                                  current_score=current_score, assistance=assistance, goal_type=goal_type)

    @dataclass(frozen=True)
    class Penalty(Incident):
        scored: bool
        current_score: Score

        @staticmethod
        def create(participant: Player, team: Team, time: Time, current_score: Score, scored: bool):
            return Incidents.Penalty(type=Types.Incident.PENALTY_KICK, participant=participant, team=team, time=time,
                                     scored=scored, current_score=current_score)

    @dataclass(frozen=True)
    class Card(Incident):
        card_type: Types.Card

        @staticmethod
        def create(participant: Player, team: Team, time: Time, card_type: Types.Card):
            return Incidents.Card(type=Types.Incident.CARD, participant=participant, team=team, time=time,
                                  card_type=card_type)

    @dataclass(frozen=True)
    class Substitution(Incident):
        participant_in: Player

        @staticmethod
        def create(participant: Player, team: Team, time: Time, participant_in: Player):
            return Incidents.Substitution(type=Types.Incident.SUBSTITUTION, participant=participant,
                                          team=team, time=time, participant_in=participant_in)


@dataclass(frozen=True)
class MatchData:
    team_home: Team
    team_away: Team
    score: Score
    venue: Venue
    incidents: List[Incidents]

    @staticmethod
    def create(team_home: Team, team_away: Team, score: Score, venue: Venue, incidents: List[Incidents]):
        return MatchData(team_home=team_home, team_away=team_away, score=score, venue=venue, incidents=incidents)

    def __str__(self):
        return f"MATCH DATA SUMMARY \n\t{self.team_home}\n\t{self.team_away}\n\t{self.score}\n\t{self.venue}\n" \
                   f"TEAM LINEUPS\n\t-> team home lineup: " + ",".join(map(str, self.team_home.lineup)) + \
               f"\n\t-> team away lineup: " + ",".join(map(str, self.team_away.lineup)) + '\n' + \
               f"INCIDENTS\n\t" + "\n\t".join(map(str, self.incidents))


# --------------------------------------------------------------------------------------------------------------------
# Data Initialization

# class handing conversion from JSON to MatchData class
class DataInitializer:
    @staticmethod
    def init_match_data(json_file_str: str) -> MatchData:
        initializer = DataInitializer()

        with open(json_file_str) as json_file:
            json_match_data = json.load(json_file)

        teams: List[Team] = initializer._init_teams(json_match_data=json_match_data)
        venue: Venue = initializer._init_venue(json_match_data=json_match_data)
        score: Score = initializer._init_score(json_match_data=json_match_data)
        incidents: List[Incidents] = initializer._init_incidents(json_match_data=json_match_data)

        return MatchData(team_home=teams[0], team_away=teams[1], venue=venue, score=score, incidents=incidents)

    @staticmethod
    def _init_teams(json_match_data: dict) -> List[Team]:
        return [DataInitializer._init_team(json_match_data=json_match_data, team_type=Types.Team.HOME),
                DataInitializer._init_team(json_match_data=json_match_data, team_type=Types.Team.AWAY)]

    @staticmethod
    def _init_team(json_match_data: dict, team_type: Types.Team) -> Team:
        id_ = int(json_match_data['participants'][str(team_type.value)]['id'])
        name = json_match_data['participants'][str(team_type.value)]['name']

        # initialize country
        country_id = int(json_match_data['participants'][str(team_type.value)]['country_id'])
        country_name = json_match_data['participants'][str(team_type.value)]['country_name']
        country = Country.create(id_=country_id, name_=country_name)

        lineup: List[Player] = []
        for p in json_match_data['lineup'][str(team_type.value)]:
            p_full_name = p['participant']['fullName']
            p_id = int(p['participant']['id'])
            p_country_id = int(p['participant']['countries'][0]['id'])
            p_country_name = p['participant']['countries'][0]['name']
            p_country: Country = Country.create(id_=p_country_id, name_=p_country_name)
            p_lineup_position_id = int(p['lineupPositionId'])
            p_number = int(p['number'])

            lineup.append(Player.create(id_=p_id, full_name=p_full_name, country=p_country,
                                        lineup_position_id=p_lineup_position_id, number=p_number))

        return Team.create(id_=id_, name=name, country=country, type_=team_type, lineup=lineup)

    @staticmethod
    def _init_score(json_match_data: dict) -> Score:
        return Score.create(goals_home=json_match_data['score'][str(Types.Team.HOME.value)]['1'],
                            goals_away=json_match_data['score'][str(Types.Team.AWAY.value)]['1'])

    @staticmethod
    def _init_venue(json_match_data: dict) -> Venue:
        name = json_match_data['venue_name']
        town = json_match_data['venue_town']
        capacity = json_match_data['venue_capacity']
        if json_match_data['venue_attendance'] is not None:
            attendance = json_match_data['venue_attendance']
        else:
            attendance = 0

        return Venue.create(name=name, town=town, capacity=capacity, attendance=attendance)

    @staticmethod
    def _init_incidents(json_match_data: dict) -> List[Incidents]:

        def _get_aux_incident(id_: int) -> (int, bool):
            for j in json_match_data['incidents']:
                if id_ == j['parentId']:
                    return j, True
            return None, False

        def _get_participant_from_id(team_: Team, id_: int) -> Player:
            for player in team_.lineup:
                if player.id == id_:
                    return player

        def _get_current_score() -> Score:
            if i['value'] is not None:
                return Score.create(goals_home=int(i['value'].split(":")[0]),
                                    goals_away=int(i['value'].split(":")[1]))
            else:
                return Score.create(0,0)

        incidents: List[Incidents] = []
        teams: List[Team] = DataInitializer._init_teams(json_match_data=json_match_data)

        for i in json_match_data['incidents']:

            time: Time = Time.create(time_base=int(i['time']),
                                     time_added=int(i['addedTime']) if i['addedTime'] is not None else 0)

            if i['eventParticipant']['participant']:
                team: Team = teams[0] if int(i['eventParticipant']['participant'][0]['id']) == teams[0].id else teams[1]
            if i['participant']['id'] is not None:
                if i['type']['name'] == 'Own Goal':
                    team: Team = teams[1] if int(i['eventParticipant']['participant'][0]['id']) == teams[0].id else \
                        teams[0]
                    participant: Player = _get_participant_from_id(team_=team, id_=int(i['participant']['id']))
                elif i['type']['name'] == 'Yellow Card' or i['type']['name'] == 'Red Card':
                    participant: Player = _get_participant_from_id(team_=team, id_=int(i['participant']['id']))
                    if participant is None:
                        # Card for coach
                        participant = Player.create(id_=int(i['participant']['id']),
                                                    full_name=i['participant']['fullName'],
                                                    country=None, number=None, lineup_position_id=None)
                else:
                    participant: Player = _get_participant_from_id(team_=team, id_=int(i['participant']['id']))

            inc_str_type: str = i['type']['name']

            if inc_str_type == "Goal":
                current_score = _get_current_score()
                aux_incident = _get_aux_incident(int(i['id']))

                if aux_incident[1]:
                    # goal with assistance
                    assistance = _get_participant_from_id(team_=team, id_=int(aux_incident[0]['participant']['id']))
                    incidents.append(Incidents.Goal.create(participant=participant, team=team, time=time,
                                                           current_score=current_score, assistance=assistance,
                                                           goal_type=Types.Goal.ASSISTANCE))
                else:
                    # solo play goal
                    incidents.append(Incidents.Goal.create(participant=participant, team=team, time=time,
                                                           current_score=current_score, assistance=None,
                                                           goal_type=Types.Goal.SOLO_PLAY))

            elif inc_str_type == "Own Goal":
                current_score = _get_current_score()
                incidents.append(Incidents.Goal.create(participant=participant, team=team, time=time,
                                                       current_score=current_score, assistance=None,
                                                       goal_type=Types.Goal.OWN_GOAL))

            elif inc_str_type == "Penalty Kick":
                aux_incident = _get_aux_incident(int(i['id']))

                scored = False
                if aux_incident[1]:
                    if aux_incident[0]['type']['name'] == "Penalty scored":
                        scored = True

                current_score = _get_current_score()

                incidents.append(Incidents.Penalty.create(participant=participant, team=team, time=time,
                                                          current_score=current_score, scored=scored))

            elif inc_str_type == "Substitution - Out":
                aux_incident = _get_aux_incident(int(i['id']))
                participant_in_id = aux_incident[0]['participant']['id']
                participant_in = _get_participant_from_id(team_=team, id_=participant_in_id)

                print(participant_in)
                print(participant)
                print('------')
                incidents.append(Incidents.Substitution.create(participant=participant, team=team, time=time,
                                                               participant_in=participant_in))

            elif inc_str_type == "Yellow Card":
                aux_incident = _get_aux_incident(int(i['id']))
                if aux_incident[1]:
                    incidents.append(Incidents.Card.create(participant=participant, team=team, time=time,
                                                           card_type=Types.Card.RED_AUTO))
                else:
                    incidents.append(Incidents.Card.create(participant=participant, team=team, time=time,
                                                           card_type=Types.Card.YELLOW))

            elif inc_str_type == "Red Card":
                if i['parentId'] is None:
                    incidents.append(Incidents.Card.create(participant=participant, team=team, time=time,
                                                           card_type=Types.Card.RED_INSTANT))

            elif inc_str_type == "Substitution - In" \
                    or inc_str_type == "Assistance" \
                    or inc_str_type == "Penalty scored" \
                    or inc_str_type == "Penalty missed" \
                    or inc_str_type == "Extended time second half"\
                    or inc_str_type == "Extended time first half"\
                    or inc_str_type == "Action not on pitch"\
                    or inc_str_type == "Goal Disallowed":
                pass

            else:
                raise ValueError("Unknown incident occurred")

        # sort incidents by time

        return incidents

# --------------------------------------------------------------------------------------------------------------------
# Document planning


@dataclass(frozen=True)
class Message:
    type: Types.Message


class Messages:
    @dataclass(frozen=True)
    class Result(Message):
        team_home: Team
        team_away: Team
        score: Score

        @staticmethod
        def create(team_home: Team, team_away: Team, score: Score):
            return Messages.Result(type=Types.Message.RESULT, team_home=team_home, team_away=team_away, score=score)

        def __str__(self):
            return f"-> Type: {self.type.name}, team_home: {self.team_home.name}, team_away: {self.team_away}" \
                f", score: {self.score}"

    @dataclass(frozen=True)
    class Card(Message):
        participant: Player
        team: Team
        time: Time
        card_type: Types.Card

        @staticmethod
        def create(participant: Player, team: Team, time: Time, card_type: Types.Card):
            return Messages.Card(type=Types.Message.CARD, participant=participant,
                                 team=team, time=time, card_type=card_type)

        def __str__(self):
            return f"-> Type: {self.type.name}, time: {self.time}, " \
                f"participant: {self.participant.full_name}, team: {self.team.name}, card_type: {self.card_type.name}"

    @dataclass(frozen=True)
    class Goal(Message):
        participant: Player
        assistance: Player
        current_score: Score
        team: Team
        time: Time
        goal_type: Types.Goal

        @staticmethod
        def create(participant: Player, team: Team, time: Time, current_score: Score,
                   assistance: Player, goal_type: Types.Goal):
            return Messages.Goal(type=Types.Message.GOAL, participant=participant, assistance=assistance,
                                 current_score=current_score, team=team, time=time, goal_type=goal_type)

        def __str__(self):
            return f"-> Type: {self.type.name}, time: {self.time}, participant: {self.participant.full_name}" \
                f", team: {self.team.name}, score: {self.current_score.goals_home}-{self.current_score.goals_away}" \
                f", goal_type: {self.goal_type}"

    @dataclass(frozen=True)
    class Substitution(Message):
        participant_out: Player
        participant_in: Player
        team: Team
        time: Time

        @staticmethod
        def create(participant_out: Player, team: Team, time: Time, participant_in: Player):
            return Messages.Substitution(type=Types.Message.SUBSTITUTION, participant_out=participant_out,
                                         participant_in=participant_in, team=team, time=time)

        def __str__(self):
            return f"-> Type: {self.type.name}, time: {self.time}, participant_out: {self.participant_out.full_name}" \
                f", participant_in: {self.participant_in.full_name}, team: {self.team.name}"

    @dataclass(frozen=True)
    class MissedPenalty(Message):
        type: Types.Message
        participant: Player
        team: Team
        time: Time

        @staticmethod
        def create(participant: Player, team: Team, time: Time):
            return Messages.MissedPenalty(type=Types.Message.PENALTY_KICK_MISSED, participant=participant,
                                          team=team, time=time)

        def __str__(self):
            return f"-> Type: {self.type.name}, time: {self.time}, participant: " \
                f"{self.participant.full_name}, team: {self.team.name}"


@dataclass(frozen=True)
class DocumentPlan:
    title: Messages
    body: List[Messages]

    @staticmethod
    def create(title: Messages, body: List[Messages]):
        return DocumentPlan(title=title, body=body)

    def __str__(self):
        return f"TITLE MESSAGE: \n\t{self.title}\nMESSAGES\n\t" + "\n\t".join(map(str, self.body))


class DocumentPlanner:

    @staticmethod
    def plan_document(match_data: MatchData) -> DocumentPlan:
        doc_planner = DocumentPlanner()
        title: Messages = doc_planner._plan_title(match_data)
        body: List[Messages] = doc_planner._plan_body(match_data)

        return DocumentPlan.create(title, body)

    @staticmethod
    def _plan_title(match_data: MatchData) -> Messages:
        return Messages.Result.create(match_data.team_home, match_data.team_away, match_data.score)

    @staticmethod
    def _plan_incident_msg(inc: Incidents) -> Messages:
        if type(inc) is Incidents.Goal:
            return Messages.Goal.create(participant=inc.participant, team=inc.team, time=inc.time,
                                        current_score=inc.current_score, assistance=inc.assistance,
                                        goal_type=inc.goal_type)
        elif inc.type == Types.Incident.PENALTY_KICK:
            if inc.scored is True:
                return Messages.Goal.create(participant=inc.participant, team=inc.team, time=inc.time,
                                            current_score=inc.current_score, assistance=None,
                                            goal_type=Types.Goal.PENALTY)
            else:
                return Messages.MissedPenalty.create(inc.participant, inc.team, inc.time)
        elif inc.type == Types.Incident.CARD:
            return Messages.Card.create(participant=inc.participant, team=inc.team, time=inc.time,
                                        card_type=inc.card_type)
        elif inc.type == Types.Incident.SUBSTITUTION:
            return Messages.Substitution.create(participant_out=inc.participant, team=inc.team, time=inc.time,
                                                participant_in=inc.participant_in)
        else:
            print("failed")

    @staticmethod
    def _plan_body(match_data: MatchData) -> List[Messages]:
        return [DocumentPlanner._plan_incident_msg(inc) for inc in match_data.incidents]

# --------------------------------------------------------------------------------------------------------------------
# Lexicalization of document plan


class Template(NamedTuple):
    type: Types.Message
    subtype: Types.MessageSubtype
    tmpl: Tmpl

    @staticmethod
    def create(type_: Types.Message, subtype: Types.MessageSubtype, tmpl: Tmpl):
        return Template(type=type_, subtype=subtype, tmpl=tmpl)


@dataclass(frozen=True)
class TemplateHandler:
    templates: List[Template]

    @staticmethod
    def create():
        return TemplateHandler(TemplateHandler._init_templates())

    @staticmethod
    def _init_templates() -> List[Template]:

        def _init_templates_result():
            # subtypes possible: WIN, DRAW, LOSE  (result from home team perspective)
            type_ = Types.Message.RESULT

            # subtype: WIN   -> templates for win of home team
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.WIN,
                                              tmpl=Tmpl('{{\'$team_home\'|morph(\'Case=Nom\', ref=1)}} '
                                                        '{{\'porazit\'|morph(\'Tense=Past\', agr=1)}} '
                                                        '{{\'$team_away\'|morph(\'Case=Acc\')}} $score.')))

            # subtype: DRAW   -> templates for draw
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.DRAW,
                                              tmpl=Tmpl('{{\'$team_home\'|morph(\'Case=Nom\', ref=1)}} '
                                                        '{{\'remizovat\'|morph(\'Tense=Past\', agr=1)}}} s '
                                                        '{{\'$team_away\'|morph(\'Case=Ins\')}} $score.')))

            # subtype: LOSS  -> templates for loss of home team
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.LOSS,
                                              tmpl=Tmpl('{{\'$team_home\'|morph(\'Case=Nom\', ref=1)}} '
                                                        '{{\'prohrát\'|morph(\'Tense=Past\', agr=1)}}} s '
                                                        '{{\'$team_away\'|morph(\'Case=Ins\')}} $score.')))

        def _init_templates_goal():
            # subtypes possible: ASSISTANCE, PENALTY, SOLO_GOAL, OWN_GOAL
            type_ = Types.Message.GOAL

            # subtype: SOLO_GOAL   -> templates for solo goals
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.SOLO_PLAY,
                                              tmpl=Tmpl('V $time. minutě dal '
                                                        '$participant_first_name $participant_last_name gól '
                                                        'a změnil stav na $score.')))

            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.SOLO_PLAY,
                                              tmpl=Tmpl('V $time. minutě vsítil '
                                                        '$participant_first_name $participant_last_name branku '
                                                        'a změnil stav na $score.')))

            # subtype: ASSISTANCE   -> templates for goals with assistance
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.ASSISTANCE,
                                              tmpl=Tmpl('V $time. minutě vsítil '
                                                        '$participant_first_name $participant_last_name branku '
                                                        'po nahrávce {{\'$assistance_first_name\'|morph(\'Case=Dat\')}}' 
                                                        ' {{\'$assistance_last_name\'|morph(\'Case=Dat\')}} '
                                                        'a zvýšil stav na $score.')))

            # subtype: OWN_GOAL  -> templates for penalty goal
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.OWN_GOAL,
                                              tmpl=Tmpl('V $time. minutě dal '
                                                        '$participant_first_name $participant_last_name gól '
                                                        'a změnil stav na $score.')))
            # subtype: PENALTY   -> templates for penalty goal
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.PENALTY,
                                              tmpl=Tmpl('V $time. minutě proměnil penaltu '
                                                        '$participant_first_name $participant_last_name.')))

        def _init_templates_substitution():
            # subtypes: None
            type_ = Types.Message.SUBSTITUTION
            templates_.append(Template.create(type_=type_, subtype=None,
                                              tmpl=Tmpl('V $time. minutě střídal hráč týmu $team '
                                                        '$participant_out_first_name $participant_out_last_name za '
                                                        '{{\'$participant_in_first_name\'|morph(\'Case=Acc\')}} ' 
                                                        '{{\'$participant_in_last_name\'|morph(\'Case=Acc\')}}.')))

        def _init_templates_card():
            # subtype: YELLOW_CARD, RED_CARD
            # substitutions: time, team, participant
            type_ = Types.Message.CARD

            # templates for red card instant
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.RED_INSTANT,
                                              tmpl=Tmpl('V $time. minutě dostal hráč týmu $team $participant_first_name'
                                                        ' $participant_last_name červenou kartu.')))

            # templates for red card auto
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.RED_AUTO,
                                              tmpl=Tmpl('V $time. minutě dostal hráč týmu $team $participant_first_name'
                                                        ' $participant_last_name červenou kartu po druhé žluté kartě.')))

            # templates for yellow card
            templates_.append(Template.create(type_=type_, subtype=Types.MessageSubtype.YELLOW,
                                              tmpl=Tmpl('V $time. minutě dostal hráč týmu $team $participant_first_name'
                                                        ' $participant_last_name žlutou kartu.')))

        def _init_templates_missed_penalty():
            type_ = Types.Message.PENALTY_KICK_MISSED
            templates_.append(Template.create(type_=type_, subtype=None,
                                              tmpl=Tmpl('V $time. minutě neproměnil '
                                                        '$participant_first_name $participant_last_name penaltu.')))

        templates_: List[Template] = []

        # initialize template for every message type
        _init_templates_result()
        _init_templates_goal()
        _init_templates_substitution()
        _init_templates_card()
        _init_templates_missed_penalty()

        return templates_

    def get_template(self, type_: Types.Message, subtype_: Types.MessageSubtype) -> Template:
        # picking valid templates
        valid_templates_type: List[Template] = [t for t in self.templates if t.type == type_]
        valid_templates: List[Template] = [t for t in valid_templates_type if ((subtype_ is None and t.subtype is None)
                                                                               or t.subtype.name == subtype_.name)]

        r = Random()
        r.seed(10)
        return r.choice(valid_templates)


class Lexicalizer:

    @staticmethod
    def lexicalize(doc_plan: DocumentPlan, match_data: MatchData) -> (str, List[str]):
        template_handler = TemplateHandler.create()
        title = Lexicalizer._lexicalize_message(doc_plan.title, template_handler)
        body = Lexicalizer._lexicalize_body(doc_plan.body, template_handler)
        return title, body

    @staticmethod
    def _lexicalize_body(body: List[Messages], template_handler: TemplateHandler) -> List[str]:
        return [Lexicalizer._lexicalize_message(msg, template_handler) for msg in body]

    @staticmethod
    def _lexicalize_message(msg: Messages, template_handler: TemplateHandler) -> str:
        tmpl_str: str

        # RESULT MSG
        if type(msg) is Messages.Result:
            template = deepcopy(template_handler.get_template(type_=Types.Message.RESULT, subtype_=msg.score.result))
            tmpl_str = template.tmpl.substitute(team_home=msg.team_home.name, team_away=msg.team_away.name,
                                                score=str(msg.score))

        # GOAL MSG
        if type(msg) is Messages.Goal:
            template = deepcopy(template_handler.get_template(type_=Types.Message.GOAL, subtype_=msg.goal_type))

            if msg.goal_type is Types.Goal.ASSISTANCE:
                tmpl_str = template.tmpl.substitute(time=str(msg.time),
                                                    participant_first_name=msg.participant.get_first_name(),
                                                    participant_last_name=msg.participant.get_last_name(),
                                                    score=str(msg.current_score),
                                                    assistance_first_name=msg.assistance.get_first_name(),
                                                    assistance_last_name=msg.assistance.get_last_name())
            else:
                tmpl_str = template.tmpl.substitute(time=str(msg.time),
                                                    participant_first_name=msg.participant.get_first_name(),
                                                    participant_last_name=msg.participant.get_last_name(),
                                                    score=str(msg.current_score),)

        # CARD MSG
        if type(msg) is Messages.Card:
            template = deepcopy(template_handler.get_template(type_=Types.Message.CARD, subtype_=msg.card_type))
            tmpl_str = template.tmpl.substitute(time=str(msg.time), team=msg.team.name,
                                                participant_first_name=msg.participant.get_first_name(),
                                                participant_last_name=msg.participant.get_last_name())

        # SUBSTITUTION MSG
        if type(msg) is Messages.Substitution:
            template = deepcopy(template_handler.get_template(type_=Types.Message.SUBSTITUTION, subtype_=None))
            tmpl_str = template.tmpl.substitute(time=str(msg.time), team=msg.team.name,
                                                participant_in_first_name=msg.participant_in.get_first_name(),
                                                participant_in_last_name=msg.participant_in.get_last_name(),
                                                participant_out_first_name=msg.participant_out.get_first_name(),
                                                participant_out_last_name=msg.participant_out.get_last_name())

        # MISSED PENALTY MSG
        if type(msg) is Messages.MissedPenalty:
            template = deepcopy(template_handler.get_template(type_=Types.Message.PENALTY_KICK_MISSED, subtype_=None))
            tmpl_str = template.tmpl.substitute(time=str(msg.time), team=msg.team.name,
                                                participant_first_name=msg.participant.get_first_name(),
                                                participant_last_name=msg.participant.get_last_name())

        return tmpl_str


# --------------------------------------------------------------------------------------------------------------------
# Realization of str from Lexicalizer

class Realizer:
    @staticmethod
    def realize_str(plain_str: (str, List[str])) -> str:
        return f'{plain_str[0]}\n' + "\n" + ("\n".join(plain_str[1]))

    @staticmethod
    def create_json_file_for_Geneea(plain_str: (str, List[str]), file_path: str):
        data = {}
        data['templates'] = []
        '''
        data['templates'].append({
            "id": "tmpl-1",
            "name": "title template",
            "body": plain_str[0]
        })
        '''

        toprint = plain_str[0] + ' '+ ' '.join(plain_str[1])
        data['templates'].append({
            "id": "tmpl-2",
            "name": "body template",
            "body": toprint
        })

        data['data'] = {}
        with open(file_path, 'w') as output_json:
            json.dump(data, output_json)

    @staticmethod
    def realize_article(plain_str: (str, List[str])) -> str:
        file_path = r'C:\Users\danra\Skola\MFF\RP\SP_SportArticleGenerator\geneea_input.json'
        Realizer.create_json_file_for_Geneea(plain_str, file_path)

        with open(file_path) as json_file:
            output_geneea: dict = Realizer.call_Geneea(json.load(json_file))

        return output_geneea['article']

    @staticmethod
    def call_Geneea(json_file: dict):
        url = 'https://generator.geneea.com/generate'
        headers = {
            'content-type': 'application/json',
            # 'Authorization': 'user_key <your user key>'
            'Authorization': os.getenv('GENJA_API_KEY')
        }
        return requests.post(url, json=json_file, headers=headers).json()


# --------------------------------------------------------------------------------------------------------------------
# TESTING ALL INPUTS
def test_inputs(directory: str):
    files_to_fix = get_files_to_fix(directory)
    if len(files_to_fix) > 50:
        print(f"Nefunguje toho hodně {len(files_to_fix)}")
        print(files_to_fix[0])
    elif len(files_to_fix) > 20:
        print("Nefunguje toho středně")
        print(files_to_fix[0])
    else:
        print(files_to_fix)


def get_files_to_fix(directory: str) -> List[str]:
    files_to_fix = []
    for filename in os.listdir(directory):
        file = os.path.join(directory, filename)
        try:
            generate_article(file, print_output=False)
        except:
            files_to_fix.append(file)
    return files_to_fix


def get_directory(filename:str) -> str:
    return os.path.dirname(filename)


# --------------------------------------------------------------------------------------------------------------------
# GENERATE ARTICLE FROM JSON
def generate_article(filename: str, print_output: bool):
    match_data: MatchData = DataInitializer.init_match_data(filename)
    print(f'{match_data} \n\n ' + '_' * 70)

    doc_plan: DocumentPlan = DocumentPlanner.plan_document(match_data)
    #print(f'{doc_plan} \n\n ' + '_' * 70)

    plain_str: (str, List[str]) = Lexicalizer.lexicalize(doc_plan, match_data)

    text: str = Realizer.realize_str(plain_str)

    if print_output:
        print(f'{match_data} \n\n ' + '_' * 70)
        print(f'{doc_plan} \n\n ' + '_' * 70)
        print(f'{plain_str} \n\n ' + '_' * 70)
        print(f'{text} \n\n ' + '_' * 70)

    # calling Geneea rest API
    article = Realizer.realize_article(plain_str)
    print(article)





# --------------------------------------------------------------------------------------------------------------------
# MAIN
def main(args):
    if args.test:
        test_inputs(get_directory(args.match_data))
    else:
        generate_article(args.match_data, print_output=True)


if __name__ == "__main__":
    args_ = parser.parse_args([] if "__file__" not in globals() else None)
    main(args_)