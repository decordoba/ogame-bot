from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from time import sleep
from lxml import etree, html
import argparse
import datetime
import json
import random
import math
import time
import sys
import msvcrt


STORAGE_LARGE_CARGO = 41250
MAXRETRY = 10
DEFAULT_EMAIL = "danieldecordobagil@hotmail.com"
LOGIN_URL = "https://lobby.ogame.gameforge.com/es_ES/?language=es"
URL = "https://s168-es.ogame.gameforge.com/game/index.php?page=ingame"
TABS = [
    "overview",  # Resumen (0)
    "supplies",  # Recursos (1)
    "facilities",  # Instalaciones (2)
    "marketplace",  # Mercado (3)
    "-",  # Mercader (4), different URL format
    "research",  # Investigación (5)
    "shipyard",  # Hangar (6)
    "defenses",  # Defensa (7)
    "fleetdispatch",  # Flota (8)
    "galaxy"  # Galaxia (9)
]
RESOURCES_NAME = {
    "M": "metal",
    "C": "crystal",
    "D": "deuterium",
    "E": "energy"
}
RESOURCES = {
    "M": "resources_metal",
    "C": "resources_crystal",
    "D": "resources_deuterium",
    "E": "resources_energy"
}
RESOURCES_BOX = {
    "M": "metal_box",
    "C": "crystal_box",
    "D": "deuterium_box",
    "E": "energy_box"
}
RESOURCES_NAME_REVERSE = {
    "metal": "M",
    "crystal": "C",
    "deuterium": "D",
    "energy": "E"
}
MINES = {
    "MM": "metalMine",
    "CM": "crystalMine",
    "DM": "deuteriumSynthesizer",
    "SP": "solarPlant",
    "MS": "metalStorage",
    "CS": "crystalStorage",
    "DS": "deuteriumStorage"
}

PLAN = [
    ["CM", "MM", "DM"],  # planet 0
    None,  # planet 1
    None  # planet 2 (you get the idea)
]

PLANETS_WITH_NO_DEFENSE = ["[5:8:9]", "[4:19:7]", "[3:16:6]", "[3:10:6]", "[2:444:6]", "[3:22:12]", "[3:22:11]", "[3:16:5]",
                          "[4:27:10]", "[5:27:4]", "[5:29:3]", "[6:127:7]", "[6:128:7]", "[6:140:10]", "[6:136:11]", "[3:22:8]", "[3:22:7]",
                          "[3:22:10]", "[3:15:9]", "[3:22:3]", "[3:22:4]"]
UNKNOWN_PLANETS_FILE = "unknown_planets.csv"


EMAIL = None
PASSWORD = None


class Refreshable(object):
    """Class to know when object was last refreshed."""
    refresh_time = None

    def refresh(self):
        self.refresh_time = datetime.datetime.now()
    
    def refreshed_since(self, date):
        """Whether class was refreshed since date.""" 
        return self.refresh_time is not None and self.refresh_time > date

    def refreshed_for(self, minutes=None, seconds=None):
        """Whether class has been refreshed for time."""
        return self.refreshed_since(datetime.datetime.now() - datetime.timedelta(minutes=minutes, seconds=seconds))

    def time_since_refresh(self):
        return datetime.datetime.now() - self.refresh_time

    def time_since_refresh_in_seconds(self):
        return self.time_since_refresh().seconds

    def refresh_str(self):
        return get_date_as_timestamp_str(self.refresh_time)


class Resource(Refreshable):
    amount = None
    production = None

    def __init__(self, driver, resource_key, verbose=True, wait_short=1):
        self.driver = driver
        self.verbose = verbose
        self.wait_short = wait_short
        self.resource_key = resource_key
        self.resource_value = RESOURCES[resource_key]
        self.resource_box = RESOURCES_BOX[resource_key]
        self.resource_name = RESOURCES_NAME[resource_key]
        self.update()

    def update(self):
        resources = self.driver.find_element_by_id("resources")
        resource_box = resources.find_element_by_id(self.resource_value)
        self.amount = int(resource_box.get_attribute("innerHTML").replace(".", "").replace(",", ""))
        # hover over resource box
        ActionChains(self.driver).move_to_element(resource_box).perform()
        tooltip = None
        retry = 0
        while retry < MAXRETRY and tooltip is None:
            try:
                tooltip = self.driver.find_element_by_class_name("resourceTooltip").get_attribute("innerHTML")
            except Exception:
                tooltip = None
                wait(self.wait_short)
            retry += 1
        self.production = int(tooltip.split("<th>Producción actual:</th>")[1].split("<span")[1].split(">")[1].split("<")[0].replace(".", "").replace(",", ""))
        if self.verbose:
            print("Resource: {}\n * Amount: {}\n * Production: {}".format(self.resource_name, self.amount, self.production))
        self.refresh()
    
    def predict(self, refresh_after=None):
        if refresh_after is not None and datetime.datetime.now() - self.refresh_time >= datetime.timedelta(minutes=refresh_after):
            self.update()
        self.prediction = self.amount + self.production * self.time_since_refresh_in_seconds() / 3600

    def __repr__(self):
        return "Amount: {} - Production: {} - Refresh: {}".format(self.amount, self.production, self.refresh_str())


class Technology(Refreshable):

    def __init__(self, driver, id, get_header=True, skip_off=True, verbose=True, wait_short=1):
        self.driver = driver
        self.id = id
        self.wait_short = wait_short
        self.verbose = verbose
        self.update(get_header=get_header, skip_off=skip_off)
    
    def update(self, get_header=True, skip_off=True):
        panel_div = self._panel_li()
        self.name = panel_div.get_attribute("class").split(" ")[1]
        self.status = panel_div.get_attribute("data-status")
        if self.status == "active":
            try:
                self.target = int(panel_div.find_element_by_class_name("targetlevel").get_attribute("data-value"))
            except Exception:
                self.target = int(panel_div.find_element_by_class_name("targetamount").get_attribute("data-value"))
            self.time_left_str = panel_div.find_element_by_tag_name("time").get_attribute("innerHTML")
            self.time_left = self._get_time_from_time_str(self.time_left_str)
        else:
            self.target = None
            self.time_left_str = None
            self.time_left = None
        try:
            self.level = int(panel_div.find_element_by_class_name("level").get_attribute("data-value"))
        except Exception:
            self.level = int(panel_div.find_element_by_class_name("amount").get_attribute("data-value"))
        if self.verbose:
            if self.target is not None:
                print("Technology: {} ({})\n * Level: {}\n * Target: {}\n * Time left: {}\n * Status: {}".format(self.name, self.id, self.level, self.target,
                                                                                                                 get_date_as_timestamp_str(self.time_left),
                                                                                                                 self.status))
            else:
                print("Technology: {} ({})\n * Level: {}\n * Target: {}".format(self.name, self.id, self.level, self.status))
        if get_header and (not skip_off or self.status != "off"):
            self._get_header_info()
        self.refresh()

    def _get_time_from_time_str(self, time_str):
        d, h, m, s = 0, 0, 0, 0
        n = 0
        for c in time_str:
            if c.isdigit():
                n = n * 10 + int(c)
            else:
                if c == "s":
                    s = n
                elif c == "m":
                    m = n
                elif c == "h":
                    h = n
                elif c == "d":
                    d = n
                elif c == " ":
                    pass
                else:
                    raise Exception("Unknown date format for {}".format(time_str))
                n = 0
        return datetime.timedelta(days=d, hours=h, minutes=m, seconds=s)

    def is_upgradable(self):
        return self.status in ["on"]

    def is_upgrading(self):
        return self.status in ["active"]

    def is_upgradable_or_will_be(self):
        return self.status in ["on", "disabled"]

    def will_be_upgradable(self):
        return self.status in ["disabled"]

    def is_not_available(self):
        return self.status in ["off"]

    def _get_header_info(self):
        for _ in range(3):  # try 3 times in case we close the panel in the first attempt (second try for good luck)
            try:
                self._panel_li().click()
            except Exception:
                scroll_down(self.driver)  # sometimes we click in chat bar, scroll down and retry
                self._panel_li().click()
            header_id = None
            header = None
            retry = 0
            while retry < MAXRETRY and (header_id is None or header_id != self.id):
                try:
                    header = self.driver.find_element_by_id("technologydetails")
                    header_id = int(header.get_attribute("data-technology-id"))
                except Exception:
                    header = None
                    header_id = None
                if header_id != self.id:
                    wait(self.wait_short)
                retry += 1
            if header_id == self.id:
                break
        content = header.find_element_by_class_name("content")
        info = content.find_element_by_class_name("information")
        try:
            info1 = info.find_element_by_class_name("narrow")
        except Exception:
            info1 = info
        self.time_prod_str = info1.find_element_by_class_name("build_duration").find_element_by_tag_name("time").get_attribute("innerHTML").strip()
        self.time_prod = self._get_time_from_time_str(self.time_prod_str)
        # this is only available if you have Comandante upgrade
        # self.build_start_str = info1.find_element_by_class_name("possible_build_start").find_element_by_tag_name("time").get_attribute("innerHTML").strip()
        # if self.build_start_str.lower() == "ahora":
        #     self.build_start = datetime.timedelta()  # 0
        # elif self.build_start_str.lower() == "desconocido":
        #     self.build_start = None
        # else:
        #     self.build_start = self._get_time_from_time_str(self.build_start_str)
        try:
            self.additional_energy = int(info1.find_element_by_class_name("additional_energy_consumption").find_element_by_tag_name("span").get_attribute("data-value").strip().replace(".", "").replace(",", ""))
        except Exception:
            try:
                self.additional_energy = int(info1.find_element_by_class_name("energy_production").find_element_by_tag_name("span").get_attribute("data-value").strip().replace(".", "").replace(",", ""))
            except Exception:
                self.additional_energy = None
        info2 = info.find_element_by_class_name("costs")
        resources = info2.find_elements_by_class_name("resource")
        self.resources = {}
        for resource in resources:
            name = resource.get_attribute("class").split(" ")[1]
            resource_key = RESOURCES_NAME_REVERSE[name] if name in RESOURCES_NAME_REVERSE else name
            self.resources[resource_key] = int(resource.get_attribute("data-value"))
        if self.verbose:
            print("Time to build: {}\nExtra energy: {}\nCost: {}".format(get_date_as_timestamp_str(self.time_prod),
                                                                         self.additional_energy, self.resources))
        wait(self.wait_short)

    def level_up(self):
        pass

    def _panel_li(self):
        return self.driver.find_element_by_css_selector("li[data-technology=\"{}\"]".format(self.id))

    def __repr__(self):
        try:
            prev = " - Time to build: {} - Extra energy: {} - Cost: {}".format(get_date_as_timestamp_str(self.time_prod),
                                                                               self.additional_energy, self.resources)
        except Exception:
            prev = ""

        if self.target is not None:
            return "Name: {} - Level: {} - Target: {} - Time left: {} - Status: {}{} - Refresh: {}".format(self.name, self.level, self.target,
                                                                                                         self.time_left, self.status, prev, self.refresh_str())
        return "Name: {} - Level: {} - Target: {}{} - Refresh: {}".format(self.name, self.level, self.status, prev, self.refresh_str())


class Panel(Refreshable):
    technologies = None

    def __init__(self, driver, tab, get_header=False, skip_off=True, verbose=True, wait_short=1):
        self.driver = driver
        self.tab = tab
        self.wait_short = wait_short
        self.verbose = verbose
        self.update(get_header=get_header, skip_off=skip_off)

    def update(self, get_header=False, skip_off=True):
        self.technologies = []
        tech_ids = []
        panel = self.driver.find_element_by_id("technologies")
        for li in panel.find_elements_by_tag_name("li"):
            tech_ids.append(int(li.get_attribute("data-technology")))
        for tech_id in tech_ids:
            self.technologies.append(Technology(self.driver, tech_id, verbose=self.verbose, wait_short=self.wait_short,
                                                get_header=get_header, skip_off=skip_off))
        self.refresh()

    def get_technology(self, name):
        return [t for t in self.technologies if t.name == name][0]

    def get_technology_by_id(self, id):
        return [t for t in self.technologies if t.id == id][0]

    def get_technology_by_position(self, index):
        return self.technologies[index]

    def get_technology_names(self):
        return [t.name for t in self.technologies]

    def __repr__(self):
        return "Tab: {} ({}) - Refresh: {}\n{}".format(self.tab, TABS[self.tab], self.refresh_str(), get_printable_list(self.technologies))


class GalaxyPlanet(Refreshable):

    def __init__(self, driver, planet_tr, galaxy_num, system_num, verbose=True, wait_short=1, wait_long=3, randomize_wait=True):
        self.driver = driver
        self.galaxy_number = galaxy_num
        self.system_number = system_num
        self.verbose = verbose
        self.wait_short = wait_short
        self.wait_long = wait_long
        self.randomize_wait = randomize_wait
        self.planet_tr = planet_tr
        self.spied = False
        self.spied_planets = 0
        self.refresh_fields()

    def refresh_fields(self):
        self.planet_number = int(self.planet_tr.find_element_by_class_name("position").get_attribute("innerHTML"))
        self.planet_name = self.planet_tr.find_element_by_class_name("planetname").get_attribute("innerHTML").strip()
        self.player = self.planet_tr.find_element_by_class_name("playername").find_element_by_tag_name("a").\
            find_element_by_tag_name("span").get_attribute("innerHTML").strip()
        self.filter = self.planet_tr.get_attribute("class")
        if self.verbose:
            print("Refreshed planet {} [{}:{}:{}] - Player {}".format(self.planet_name,
                                                                      self.galaxy_number, self.system_number,
                                                                      self.planet_number, self.player))
        self.refresh()

    def update(self):
        self.get_planet_tr()
        self.refresh_fields()

    def spy(self, only_if_never_spied=True, retry=3, planets_spied=0):
        if not only_if_never_spied or not self.spied:
            self.get_planet_tr()
            try:
                self.planet_tr.find_element_by_class_name("espionage").click()
            except Exception:
                scroll_down(self.driver)  # sometimes we click in chat bar or somwwhere else, scroll down and retry
                try:
                    self.planet_tr.find_element_by_class_name("espionage").click()
                except Exception:
                    print("Unknown error, skipped spionage")
                    return
            ActionChains(self.driver).move_to_element(self.driver.find_element_by_id("pageReloader")).perform()  # move mouse out of the way
            random_wait = 0 if not self.randomize_wait else random.random() - 0.5
            wait(self.wait_short + random_wait)
            try:
                fleet_going = self.planet_tr.find_elements_by_class_name("fleetAction")
            except Exception:
                self.get_planet_tr()
                fleet_going = self.planet_tr.find_elements_by_class_name("fleetAction")
            if len(fleet_going) > 0:
                self.spied = True
                self.spied_planets += 1
                if self.verbose:
                    print("Spied successfully ({}): {}".format(self.spied_planets + planets_spied, self))
            elif retry > 0:
                random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
                wait(self.wait_long + random_wait)
                self.spy(only_if_never_spied=only_if_never_spied, retry=retry - 1, planets_spied=planets_spied)
            elif self.verbose:
                print("Could not spy: {}".format(self))
        elif self.verbose:
            print("Already spied before: {}".format(self))
        return self.spied_planets

    def get_planet_tr(self):
        self.get_current_galaxy_and_system()
        if self.galaxy_number != self.current_galaxy_num or self.system_number != self.current_system_num:
            self.go_to_galaxy_and_system(self.galaxy_number, self.system_number)
        planets_tr = self.driver.find_element_by_id("galaxytable").find_element_by_tag_name("tbody").find_elements_by_tag_name("tr")
        found = False
        for i, p in enumerate(planets_tr):
            try:
                tmp_planet_number = p.find_element_by_class_name("position").get_attribute("innerHTML")
            except Exception:
                p = self.driver.find_element_by_id("galaxytable").find_element_by_tag_name("tbody").find_elements_by_tag_name("tr")[i]
                tmp_planet_number = p.find_element_by_class_name("position").get_attribute("innerHTML")
            if tmp_planet_number == str(self.planet_number):
                self.planet_tr = p
                found = True
                break
        if not found:
            self.planet_tr = None
    
    def __repr__(self):
        return "Planet {} [{}:{}:{}] - Player {}".format(self.planet_name,
                                                         self.galaxy_number, self.system_number,
                                                         self.planet_number, self.player)
        
    def get_current_galaxy_and_system(self):
        header = self.driver.find_element_by_id("galaxyHeader")
        galaxy_num = header.find_element_by_id("galaxy_input").get_attribute("value")
        system_num = header.find_element_by_id("system_input").get_attribute("value")
        if galaxy_num == "" or system_num == "":
            self.refresh_panel()
            header = self.driver.find_element_by_id("galaxyHeader")
            galaxy_num = header.find_element_by_id("galaxy_input").get_attribute("value")
            system_num = header.find_element_by_id("system_input").get_attribute("value")
        galaxy_num, system_num = int(galaxy_num), int(system_num)
        self.current_galaxy_num = galaxy_num
        self.current_system_num = system_num
        return galaxy_num, system_num

    def go_to_galaxy_and_system(self, galaxy_num=None, system_num=None):
        self.refresh_panel()
        header = self.driver.find_element_by_id("galaxyHeader")
        if galaxy_num is not None:
            galaxy_input = header.find_element_by_id("galaxy_input")
            galaxy_input.clear()
            galaxy_input.send_keys(str(galaxy_num))
        if system_num is not None:
            system_input = header.find_element_by_id("system_input")
            system_input.clear()
            system_input.send_keys(str(system_num))
        random_wait = 0 if not self.randomize_wait else random.random() - 0.5
        wait(self.wait_short + random_wait)
        self.get_current_galaxy_and_system()

    def refresh_panel(self):
        ActionChains(self.driver).key_down(Keys.LEFT).key_up(Keys.LEFT).key_down(Keys.RIGHT).key_up(Keys.RIGHT).perform()
    
    def position(self):
        return "[{}:{}:{}]".format(self.galaxy_number, self.system_number, self.planet_number)


class GalaxyPanel(Refreshable):
    
    def __init__(self, driver, tab=9, verbose=True, wait_short=1, wait_long=3, randomize_wait=True):
        self.driver = driver
        self.tab = tab
        self.wait_short = wait_short
        self.wait_long = wait_long
        self.randomize_wait = randomize_wait
        self.verbose = verbose
        self.planets = {}

    def spy_around(self, number_systems, filters=["inactive"], skip_middle=None):
        self.get_current_galaxy_and_system()
        first_system = max(self.current_system_num - int(number_systems / 2), 1)
        last_system = first_system + number_systems - 1
        planets_spied = 0
        if skip_middle is None:
            planets_spied += self.spy_range(first_system, last_system)
        elif skip_middle < number_systems:
            first_system_middle = max(self.current_system_num - int(skip_middle / 2), 1)
            last_system_middle = first_system + skip_middle - 1
            planets_spied += self.spy_range(first_system, first_system_middle)
            planets_spied += self.spy_range(last_system_middle, last_system)
        return planets_spied

    def spy_range(self, first_system, last_system, filters=["inactive"]):
        assert first_system <= last_system and last_system < 500 and first_system > 0
        self.go_to_galaxy_and_system(galaxy_num=None, system_num=first_system)
        planets_spied = 0
        planets_actually_spied = 0
        while self.current_system_num <= last_system:
            new_planets_spied, new_planets_actually_spied = self.spy_current_system(filters=filters, planets_spied=planets_actually_spied)
            planets_spied += new_planets_spied 
            planets_actually_spied += new_planets_actually_spied
            random_wait = 0 if not self.randomize_wait else random.random() - 0.5
            wait(self.wait_short + random_wait)
            self.move("R")
        return planets_spied

    def spy_current_system(self, filters=["inactive"], planets_spied=0):
        # Other filters: inactive, strong, vacation, newbie.
        self.get_current_galaxy_and_system()
        if self.verbose:
            print("Looking at galaxy {}, system {}".format(self.current_galaxy_num, self.current_system_num))

        # get planets
        retry = 3
        while retry > 0:
            try:
                self.planets_tr = self.driver.find_element_by_id("galaxytable").find_element_by_tag_name("tbody").find_elements_by_tag_name("tr")
                if filters is None or filters is []:
                    self.filtered_planets_tr = self.planets_tr
                else:
                    self.filtered_planets_tr = []
                    for p in self.planets_tr:
                        planet_class = p.get_attribute("class")
                        for f in filters:
                            if f in planet_class:
                                self.filtered_planets_tr.append(p)
                                break
                break
            except Exception:
                retry -= 1
        new_planets = []
        for p in self.filtered_planets_tr:
            new_planets.append(GalaxyPlanet(self.driver, p, self.current_galaxy_num, self.current_system_num, verbose=self.verbose, wait_short=self.wait_short, wait_long=self.wait_long))
        if self.verbose:
            print("Found {} planets to spy".format(len(new_planets)))
        for p in new_planets:
            pos = p.position()
            if pos not in self.planets:
                self.planets[pos] = p
            planets_spied += self.planets[pos].spy(planets_spied=planets_spied)
        self.refresh()
        if self.verbose:
            print("")
        return len(new_planets), planets_spied
    
    def get_current_galaxy_and_system(self):
        header = self.driver.find_element_by_id("galaxyHeader")
        galaxy_num = header.find_element_by_id("galaxy_input").get_attribute("value")
        system_num = header.find_element_by_id("system_input").get_attribute("value")
        if galaxy_num == "" or system_num == "":
            self.refresh_panel()
            header = self.driver.find_element_by_id("galaxyHeader")
            galaxy_num = header.find_element_by_id("galaxy_input").get_attribute("value")
            system_num = header.find_element_by_id("system_input").get_attribute("value")
        galaxy_num, system_num = int(galaxy_num), int(system_num)
        self.current_galaxy_num = galaxy_num
        self.current_system_num = system_num
        return galaxy_num, system_num

    def go_to_galaxy_and_system(self, galaxy_num=None, system_num=None):
        self.refresh_panel()
        header = self.driver.find_element_by_id("galaxyHeader")
        if galaxy_num is not None:
            galaxy_input = header.find_element_by_id("galaxy_input")
            galaxy_input.clear()
            galaxy_input.send_keys(str(galaxy_num))
        if system_num is not None:
            system_input = header.find_element_by_id("system_input")
            system_input.clear()
            system_input.send_keys(str(system_num))
        ActionChains(self.driver).key_down(Keys.ENTER).key_up(Keys.ENTER).perform()
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)
        self.get_current_galaxy_and_system()

    def move(self, direction="R"):
        key = None
        if direction.upper() == "L":
            key = Keys.LEFT
        elif direction.upper() == "R":
            key = Keys.RIGHT
        elif direction.upper() == "U":
            key = Keys.UP
        elif direction.upper() == "D":
            key = Keys.DOWN
        if key is not None:
            ActionChains(self.driver).key_down(key).key_up(key).perform()
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)
        self.get_current_galaxy_and_system()
    
    def refresh_panel(self):
        ActionChains(self.driver).key_down(Keys.LEFT).key_up(Keys.LEFT).key_down(Keys.RIGHT).key_up(Keys.RIGHT).perform()

    def __repr__(self):
        return "Planets recorded: {} - Refresh: {}".format(len(self.planets), self.refresh_str())


class Message(Refreshable):

    def __init__(self, driver, msg_time, msg_id, msg_number, name_and_coords, coords, metal, crystal, deuterium, defense, fleet, attack_href, verbose=True):
        self.driver = driver
        self.msg_time = msg_time
        self.msg_id = msg_id
        self.msg_number = msg_number
        self.name_and_coords = name_and_coords
        self.coords = coords
        self.metal = metal
        self.crystal = crystal
        self.deuterium = deuterium
        self.resources = self.metal + self.crystal + self.deuterium
        self.defense = defense
        self.fleet = fleet
        self.attack_href = attack_href
        self.attacked = None
        self.verbose = verbose
        if self.verbose:
            print("{}. {}: {}\n * Resources: {} (M {} - C {} - D {})".format(self.msg_number, self.msg_time, self.name_and_coords, self.resources, self.metal, self.crystal, self.deuterium))        
            if defense is not None and (self.defense > 0 or self.fleet > 0):
                print(" * Flota: {}, Defensa: {}".format(self.fleet, self.defense))

    def attack(self, save_attacks=True):
        go_to_url(self.driver, self.attack_href)
        self.attacked = datetime.datetime.now()
        if self.verbose:
            print("Clicked: {}".format(self.attack_href))
        if save_attacks:
            line = "{},{},{},{},{},{},{},{}\n".format(self.msg_time, self.coords, self.resources, self.metal, self.crystal, self.deuterium, self.defense, self.attack_href)
            with open("attacks.csv", "a+") as f:
                f.write(line)

    def is_defended(self):
        if self.defense is None or self.fleet is None:
            # use this for planets with a level of spionage tech that does not allow us to see defense but that have no defense
            if self.coords in PLANETS_WITH_NO_DEFENSE:
                print("This planet has no defense according to our data! Many rebels gave their lives to acquire this intel, use it wisely.")
                return False
            with open(UNKNOWN_PLANETS_FILE, "a+") as f:
                f.write(",".join([time.strftime('%Y/%m/%d %H:%M'), self.coords, self.attack_href]) + "\n")
            print("This planet may have defense! --------------------------------------------------------------------------------")
            return True
        return self.defense > 0 or self.fleet > 0

    def get_num_cargos(self, storage=STORAGE_LARGE_CARGO, resources_percentage=50):
        return math.ceil(self.resources * resources_percentage / 100 / storage)

    def __repr__(self):
        s = ""
        s += "{}. {}\n * Planet: {}\n * Resources: {}".format(self.msg_number, self.msg_time, self.name_and_coords, self.resources)
        s += "\n * Metal: {}\n * Cristal: {}\n * Deuterio: {}".format(self.metal, self.crystal, self.deuterium)
        if self.defense is not None:
            s += "\n * Flota: {}\n * Defensa: {}".format(self.fleet, self.defense)
        if self.attacked is not None:
            s += "\n * Attacked: Yes ({})".format(self.attacked)
        return s


class MessagePanel(Refreshable):

    def __init__(self, driver, verbose=True, wait_short=1, wait_long=3, randomize_wait=True):
        self.driver = driver
        self.wait_short = wait_short
        self.wait_long = wait_long
        self.randomize_wait = randomize_wait
        self.verbose = verbose
        self.open_messages()
        self.message_ids = set()
        self.messages = {}
        self.resources = {
            "R": {},
            "M": {},
            "C": {},
            "D": {}
        }
        self.attacked_number = 0

    def attack_number(self, number, send_fleet=False, ignore_if_defended=True, spy_planet=False):
        """spy_planet spies planet with 5 probes instead of attacking."""
        msg = self.get_message_by_number(number)
        if self.verbose:
            print("About to attack:\n{}".format(msg))
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)
        while True:
            msg.attack()
            random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
            wait(self.wait_long + random_wait)
            target = self.driver.find_element_by_id("fleet1").find_element_by_id("statusBarFleet").find_element_by_class_name("targetName").get_attribute("innerHTML").split("]")[0] + "]"
            if self.verbose:
                print("Target planet:", msg.coords, "==", target, "?")
            if target == msg.coords:
                break
        num_cargos_needed = msg.get_num_cargos()
        panel = Panel(self.driver, tab=8, verbose=False)
        if not spy_planet:
            cargos = panel.get_technology("transporterLarge")
            if cargos.level == 0:
                print("No cargos available")
                # raise Exception("No cargos available")
                return False
            input_field = self.driver.find_element_by_id("technologies").find_element_by_class_name("transporterLarge").find_element_by_tag_name("input")
            input_field.clear()
            input_field.send_keys(str(num_cargos_needed))
            if self.verbose:
                print("Using {} large cargos".format(num_cargos_needed))
            if msg.is_defended():
                fighters = panel.get_technology("fighterHeavy")
                if fighters.level > 0 and not ignore_if_defended:
                    input_field = self.driver.find_element_by_id("technologies").find_element_by_class_name("fighterHeavy").find_element_by_tag_name("input")
                    input_field.clear()
                    input_field.send_keys(str(1))
                else:
                    print("Will not attack, too dangerous")
                    return True
        else:
            probes = panel.get_technology("espionageProbe")
            probes_to_send = 5
            if probes.level < probes_to_send:
                print("Not enough probes available")
                return False
            input_field = self.driver.find_element_by_id("technologies").find_element_by_class_name("espionageProbe").find_element_by_tag_name("input")
            input_field.clear()
            input_field.send_keys(str(probes_to_send))
        try:
            self.driver.find_element_by_id("continueToFleet2").click()
        except Exception:
            scroll_down(self.driver)
            self.driver.find_element_by_id("continueToFleet2").click()
        random_wait = 0 if not self.randomize_wait else random.random() - 0.5
        wait(self.wait_short + random_wait)
        try:
            self.driver.find_element_by_id("continueToFleet3").click()
        except Exception:
            scroll_down(self.driver)
            self.driver.find_element_by_id("continueToFleet3").click()
        if spy_planet:
            # change attack mode to spy
            self.driver.find_element_by_id("missionButton6").click()
            wait(1)
        if send_fleet:
            random_wait = 0 if not self.randomize_wait else random.random() - 0.5
            wait(self.wait_short + random_wait)
            try:
                self.driver.find_element_by_id("sendFleet").click()
                wait(2)
            except Exception:
                scroll_down(self.driver)
                try:
                    self.driver.find_element_by_id("sendFleet").click()
                except Exception:
                    button = self.driver.find_element_by_id("sendFleet")
                    self.driver.execute_script("arguments[0].scrollIntoView();", button)
                    wait(2)
                    button.click()
            self.attacked_number += 1
            if self.verbose:
                print("Attacked ({})!\n".format(self.attacked_number))
        return True

    def get_message_by_coords(self, coords):
        return [self.messages[m] for m in self.messages if self.messages[m].coords == coords][0]

    def get_message_by_number(self, number):
        return [self.messages[m] for m in self.messages if self.messages[m].msg_number == number][0]

    def get_message_by_id(self, id):
        return self.messages[id]

    def open_messages(self):
        self.driver.find_element_by_id("notificationbarcomponent").find_element_by_class_name("messages").click()
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)

    def erase_all_messages(self):
        self.driver.find_element_by_class_name("trash_box").find_element_by_class_name("not_in_trash").click()
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)

    def move_message(self, operation=">"):
        # operations: <<, <, >, >>
        nav = self.driver.find_element_by_id("fleetsgenericpage").find_element_by_class_name("pagination")
        paginators = nav.find_elements_by_class_name("paginator")
        if operation == ">":
            paginator = paginators[2]
        elif operation == "<":
            paginator = paginators[1]
        elif operation == "<<":
            paginator = paginators[0]
        elif operation == ">>":
            paginator = paginators[3]
        try:
            paginator.click()
        except Exception:
            scroll_down(self.driver)  # go down to click paginator
            paginator.click()
        if self.verbose:
            print("Moving page in direction:", operation)
        random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
        wait(self.wait_long + random_wait)

    def get_page_number(self):
        nav = self.driver.find_element_by_id("fleetsgenericpage").find_element_by_class_name("pagination")
        self.current_page, self.num_pages = nav.find_element_by_class_name("curPage").get_attribute("innerHTML").split("/")
        self.current_page, self.num_pages = int(self.current_page), int(self.num_pages)

    def get_messages(self, erase_message=False, debug_info=False):
        try:
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
        except Exception:
            self.open_messages()
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
        for i, msg in enumerate(messages):
            msg_id = msg.get_attribute("data-msg-id")
            msg_id_name = msg_id
            if msg_id_name in self.message_ids:
                allow_repeated_ids = False
                for n in range(1000 if allow_repeated_ids else 0):
                    tmp_id = msg_id_name + "_{}".format(n)
                    if tmp_id not in self.message_ids:
                        msg_id_name = tmp_id
                        if debug_info:
                            print("Message id changed to", msg_id_name)
                        break
                if "_" not in msg_id_name:
                    print("All ids used")
                    continue
            if self.verbose:
                print("Reading message {} with message id {}".format(i + 1, msg_id))
            head = msg.find_element_by_class_name("msg_head")
            name_and_coords = "[" + head.find_element_by_class_name("msg_title").find_element_by_tag_name("a").get_attribute("innerHTML").split("</figure>")[-1]
            coords = "[" + name_and_coords.split("[")[-1]
            msg_time = head.find_element_by_class_name("fright").find_element_by_class_name("msg_date").get_attribute("innerHTML")

            content = msg.find_element_by_class_name("msg_content")
            lines = content.find_elements_by_class_name("compacting")
            m, c, d = None, None, None
            for line in lines:
                spans = line.find_elements_by_class_name("ctn")
                if len(spans) != 2:
                    if debug_info:
                        print("Different to 2")
                        for i, span in enumerate(spans):
                            print(i)
                            show_html(span)
                    continue
                try:
                    resources = spans[0].find_elements_by_class_name("resspan")
                    m = int(resources[0].get_attribute("innerHTML").split("Metal: ")[1].replace(".", "").replace(",", ""))
                    c = int(resources[1].get_attribute("innerHTML").split("Cristal: ")[1].replace(".", "").replace(",", ""))
                    d = int(resources[2].get_attribute("innerHTML").split("Deuterio: ")[1].replace(".", "").replace(",", ""))
                except Exception as e:
                    if debug_info:
                        print("Exception 1:", str(e))
                    continue
            defense, fleet = None, None
            for line in lines:
                spans = line.find_elements_by_class_name("ctn")
                if len(spans) != 2:
                    if debug_info:
                        print("Different to 2")
                        for i, span in enumerate(spans):
                            print(i)
                            show_html(span)
                    continue
                if "tooltipLeft" not in spans[0].get_attribute("class") or "tooltipRight" not in spans[1].get_attribute("class"):
                    if debug_info:
                        print("No tooltips")
                        show_html(spans[0])
                        show_html(spans[1])
                    continue
                try:
                    fleet = int(spans[0].get_attribute("innerHTML").split("Flotas: ")[1].replace(".", "").replace(",", ""))
                    defense = int(spans[1].get_attribute("innerHTML").split("Defensa: ")[1].replace(".", "").replace(",", ""))
                except Exception as e:
                    if debug_info:
                        print("Exception 2:", str(e))
                    continue
            attack_href = msg.find_element_by_class_name("msg_actions").find_element_by_class_name("icon_attack").find_element_by_xpath("./..").get_attribute("href")
            self.message_ids.add(msg_id_name)  # never read same message twice
            if d is not None:
                self.messages[msg_id_name] = Message(self.driver, msg_time, msg_id, len(self.messages), name_and_coords, coords, m, c, d, defense, fleet, attack_href, verbose=self.verbose)
                res = m + c + d
                for res, res_key in zip((m, c, d, m + c + d), ("M", "C", "D", "R")):
                    if res not in self.resources[res_key]:
                        self.resources[res_key][res] = []
                    self.resources[res_key][res].append(msg_id_name)
            if erase_message:
                try:
                    msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()
                except Exception:
                    try:
                        self.driver.find_element_by_class_name("tpd-content").find_element_by_class_name("close-tooltip").click()  # close tooltip
                    except Exception as e:
                        if debug_info:
                            print("Exception 3:", str(e))
                    msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()

    def show_messages(self, resource="R"):
        resources = sorted(self.resources[resource])
        for key in resources:
            msg_ids = self.resources[resource][key]
            for msg_id in msg_ids:
                print(self.messages[msg_id])
    
    def get_first_not_attacked_message(self, resource="R"):
        resources = sorted(self.resources[resource], reverse=True)
        for key in resources:
            msg_ids = self.resources[resource][key]
            for msg_id in msg_ids:
                if self.messages[msg_id].attacked:
                    continue
                return self.messages[msg_id]

    def get_all_messages_old(self):
        self.get_page_number()
        for _ in range(self.num_pages):
            self.get_messages(erase_message=True)
            self.open_messages()

    def get_all_messages(self):
        self.get_page_number()
        for _ in range(self.num_pages):
            self.get_messages(erase_message=False)
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
            for i, msg in enumerate(messages):
                print("Erasing message")
                try:
                    msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()
                except Exception:
                    try:
                        self.driver.find_element_by_class_name("tpd-content").find_element_by_class_name("close-tooltip").click()  # close tooltip
                    except Exception:
                        pass
                    try:
                        msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()
                    except Exception:
                        self.driver.execute_script("arguments[0].scrollIntoView();", msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a"))
                    msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()
            self.open_messages()


class Planet(Refreshable):
    tab = None
    panels = None

    def __init__(self, driver, idx, planet_id, use_current_tab=False, get_panels=True,
                 verbose=True, wait_short=1, randomize_wait=True, page_refresh_rate=15, get_resources=False):
        assert idx is not None
        self.driver = driver
        self.index = idx
        self.id = planet_id
        self.verbose = verbose
        self.wait_short = wait_short  # seconds
        self.randomize_wait = randomize_wait
        self.page_refresh_rate = page_refresh_rate  # minutes
        self._get_planet_info()
        self._open_planet_in_tab(use_current_tab)
        if get_resources:
            self._get_resources()
        if get_panels:
            self._get_tab_panels()
        else:
            self.panels = None

    def spy_close_inactive_planets(self, number_systems=10, skip_middle=None):
        """ATTACK INACTIVE PLANETS. Spy all planets around."""
        self.switch_to_planet_tab()
        self._go_to_tab(8)  # Hangar
        panel = Panel(self.driver, tab=8, verbose=False)
        if panel.get_technology("espionageProbe").level < 10:
            raise Exception("Build more probes to spy efficiently")
        self._go_to_tab(9)  # Galaxia
        self.galaxy = GalaxyPanel(self.driver)
        planets_spied = self.galaxy.spy_around(number_systems, skip_middle=skip_middle)
        if self.verbose:
            print("Planets Spied:", planets_spied, "\n")

    def get_number_cargos(self):
        """ATTACK INACTIVE PLANETS. Used to get number large cargos."""
        self.switch_to_planet_tab()
        self.get_panel(6)  # Hangar
        self.num_cargos = self.panels[6].get_technology("transporterLarge").level
        print("Number of large cargos:", self.num_cargos)

    def _get_resources(self):
        self.resources = {}
        if self.verbose:
            print("Gathering resources")
        for resource_key in ["M", "C", "D", "E"]:
            self.resources[resource_key] = Resource(self.driver, resource_key, verbose=self.verbose, wait_short=self.wait_short)
    
    def predict_resources(self):
        for resource_key in self.resources:
            self.resources[resource_key].predict(refresh_after=self.page_refresh_rate)

    def _get_tab_panels(self):
        for tab in [1, 2, 5, 6, 7]:
            self.get_panel(tab)

    def get_panel(self, tab):
        if self.verbose:
            print("Gathering information for panel {} ({})".format(TABS[tab], tab))
        self._go_to_tab(tab)
        if self.panels is None:
            self.panels = {}
        self.panels[tab] = Panel(self.driver, tab, verbose=self.verbose, wait_short=self.wait_short)
        random_wait = 0 if not self.randomize_wait else random.random() - 0.5
        wait(self.wait_short + random_wait)

    def _get_planet_info(self):
        planet_div = self._planet_div()
        self.name = planet_div.find_element_by_class_name("planet-name").get_attribute("innerHTML")
        self.coords_str = planet_div.find_element_by_class_name("planet-koords").get_attribute("innerHTML")
        self.coords = self.coords_str.split(":")
        assert self.coords[0].startswith("[") and self.coords[2].endswith("]") and len(self.coords) == 3
        self.coords = [int(self.coords[0][1:]), int(self.coords[1]), int(self.coords[2][:-1])]

    def click_planet_if_not_current(self):
        if not self._is_planet_highlighted():
            self._click_planet()

    def refresh_page(self):
        self._click_planet()

    def _open_planet_in_tab(self, use_current_tab):
        if use_current_tab:
            self._click_planet()
            self.window = self.driver.current_window_handle
        else:
            windows_before = self.driver.window_handles
            self._click_planet(with_ctrl=True)
            windows_after = self.driver.window_handles
            while len(windows_before) == len(windows_after):
                random_wait = 0 if not self.randomize_wait else random.random() - 0.5
                wait(self.wait_short + random_wait)
                windows_after = self.driver.window_handles
            self.window = [w for w in windows_after if w not in windows_before][0]
        self.switch_to_planet_tab()

    def switch_to_planet_tab(self):
        self.driver.switch_to_window(self.window)

    def _is_planet_highlighted(self):
        return "hightlightPlanet" in self._planet_div().get_attribute("class")

    def _planet_str(self):
        return "{} {}".format(self.name, self.coords_str)

    def _click_planet(self, with_ctrl=False):
        self.driver.execute_script("arguments[0].scrollIntoView();", self._planet_div())
        if not with_ctrl:
            self._planet_div().click()
        else:
            ActionChains(self.driver).key_down(Keys.CONTROL).click(self._planet_div()).key_up(Keys.CONTROL).perform()
        self.refresh()
        if self.verbose:
            print ("Clicking on Planet: {}{}".format(self._planet_str(), " - Opening in new tab" if with_ctrl else ""))

    def _go_to_tab(self, tab=None):
        if self.tab is None or self.tab != tab or self.refresh_time + datetime.timedelta(minutes=self.refresh_time) < datetime.datetime.now():
            url = URL + "&component={}"
            go_to_url(self.driver, url.format(TABS[tab]))
            self.refresh()
            if self.verbose:
                print ("Clicking on Tab: {} ({})".format(TABS[tab], tab))
            self._click_planet()

    def _planet_div(self):
        return self.driver.find_element_by_id(self.id)


class OGame(object):

    def __init__(self, driver, verbose=True, wait_long=3, wait_short=1):
        # variables from input variables
        self.driver = driver
        self.verbose = verbose
        self.wait_long = wait_long
        self.wait_short = wait_short

        self._get_planets()
        self._initialize_planets()

    def _get_planets(self):
        self.planets_ids = []
        planets = self.driver.find_element_by_id("planetList")
        for planet_div in planets.find_elements_by_tag_name("div"):
            self.planets_ids.append(planet_div.get_attribute("id"))
        self.num_planets = len(self.planets_ids)
        if self.verbose:
            print("Found {} planets:".format(self.num_planets))
            for i, planet_id in enumerate(self.planets_ids):
                print(" * Idx: {} - Id: {}".format(i, planet_id))

    def _initialize_planets(self):
        self.planets = []
        for i, planet_id in enumerate(self.planets_ids):
            planet = Planet(self.driver, i, planet_id, use_current_tab=True,
                            verbose=self.verbose, wait_short=self.wait_short, get_panels=False)
            self.planets.append(planet)

    def spy_close_inactive_planets(self, planet_index=None, number_systems=30, skip_middle=None):
        if planet_index is None:
            for planet in self.planets:
                planet.spy_close_inactive_planets(number_systems, skip_middle)
        else:
            self.planets[planet_index].spy_close_inactive_planets(number_systems, skip_middle)
    
    def read_all_spionage_messages(self):
        self.msgs = MessagePanel(self.driver)
        self.msgs.get_all_messages()
        self.msgs.show_messages()
    
    def erase_all_messages(self):
        msgs = MessagePanel(self.driver)
        msgs.erase_all_messages()
    
    def spy_around_and_read_messages(self, planet_index, number_systems, skip_middle=None, erase_messages_before=True):
        if erase_messages_before:
            self.erase_all_messages()
        if self.verbose:
            print("Spying...")
        self.spy_close_inactive_planets(planet_index, number_systems, skip_middle)
        if self.verbose:
            print("Reading messages...")
        wait(25)
        self.read_all_spionage_messages()

    def spy_and_attack_best(self, planet_index, number_attacks, number_systems_to_spy=None, skip_middle=None, erase_messages_before=True, resource="R"):
        if number_systems_to_spy is not None:
            self.spy_around_and_read_messages(planet_index, number_systems_to_spy, skip_middle=skip_middle, erase_messages_before=erase_messages_before)
        if self.verbose:
            print("Attacking...")
        for i in range(number_attacks):
            print("Attack #{}".format(i + 1))
            msg = self.msgs.get_first_not_attacked_message(resource=resource)
            if msg is None:
                print("No more planets to attack!")
                break
            success = self.msgs.attack_number(msg.msg_number, send_fleet=True)
            if not success:
                break
            wait(3)


def wait(seconds=5, verbose=True):
    if verbose:
        print("Waiting {:.2f}s...".format(seconds))
    sleep(seconds)
    if verbose and seconds >= 10:
        print("Done")


def get_printable_list(list):
    return json.dumps(list, indent=4)


def get_printable_dict(dict, order=None):
    if order is None:
        return json.dumps(dict, indent=4, sort_keys=True)
    else:
        s = ""
        s += "{\n"
        for i, key in enumerate(order):
            s += "    \"{}\": {}{}".format(key, dict[key], "," if i < len(dict) - 1 else "") + "\n"
        for j, key in enumerate(dict):
            if key not in order:
                s += "    \"{}\": {}{}".format(key, dict[key], "," if i + j < len(dict) - 1 else "") + "\n"
        s += "}"
        return s


def show_html(selenium_object, pretty=True):
    print("Tag:", selenium_object.tag_name)
    html_str = selenium_object.get_attribute("innerHTML")
    if not pretty:
        print(html_str)
    else:
        print(etree.tostring(html.fromstring(html_str), encoding='unicode', pretty_print=True))


def parse_args(default_email=DEFAULT_EMAIL):
    parser = argparse.ArgumentParser(description='Enter credentials')
    parser.add_argument('--email', default=default_email, help="Default: {}".format(default_email))
    parser.add_argument('password')
    return parser.parse_args()


def login(driver=None, maximize=True):
    print("======================================")
    print("LOGGING IN...")

    global EMAIL
    if EMAIL is None:
        print("No email/username provided. Please type your email to log into the game.")
        EMAIL = input(">> ")
    global PASSWORD
    if PASSWORD is None:
        print("No password provided. Please type your password to log into the game.")
        PASSWORD = input(">> ")

    email = EMAIL
    password = PASSWORD
    if email is None or password is None:
        args = parse_args(DEFAULT_EMAIL)
        email = args.email if email is None else email
        password = args.password if password is None else password
    print("Email:", email)
    print("Password:", "*" * len(password))

    try:
        driver.current_url
    except Exception as exception:
        if driver is None or exception.__class__.__name__ == "WebDriverException":
            print("Starting browser...")
            driver = start_browser()
    
    if maximize:
        driver.maximize_window()

    if not driver.current_url.startswith(LOGIN_URL):
        print("Loading login page...")
        go_to_url(driver, LOGIN_URL)  # overview
        wait(2)

    print_page_info(driver)

    # close publicity
    print("Closing publicity...")
    try:
        close_button = driver.find_elements_by_class_name("openX_int_closeButton")[0]
        close_button_link = close_button.find_element_by_tag_name("a")
        close_button_link.click()
    except Exception:
        print("Publicity was already closed!")

    wait(2)

    # switch to Iniciar Sesion
    print("Switching to 'Iniciar Sesión' tab...")
    tabs = driver.find_elements_by_class_name("tabs")[0]
    text = tabs.find_elements_by_xpath("//*[contains(text(), 'Iniciar sesión')]")[0]
    button = text.find_element_by_xpath("./..")
    show_html(button)
    button.click()

    wait(2)

    # enter credentials
    print("Entering credentials...")
    form = driver.find_elements_by_id("loginForm")[0]
    email_input = form.find_element_by_name("email")
    email_input.clear()
    email_input.send_keys(email)
    password_input = form.find_element_by_name("password")
    password_input.clear()
    password_input.send_keys(password)

    wait(2)

    # send credentials
    print("Clicking 'Iniciar Sesión' button...")
    form.find_element_by_tag_name("button").click()

    wait(2)

    # next screen
    print("Clicking 'Jugado por última vez' button...")
    try:
        main_window = driver.current_window_handle
        text = driver.find_elements_by_xpath("//*[contains(text(), 'Jugado por última vez')]")[0]
        button = text.find_element_by_xpath("./..")
        button.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", button)
            button.click()
        except Exception:
            driver.execute_script("window.scrollBy(0,document.body.scrollHeight)")
            button.click()

    wait(2)

    # change tabs
    print("Switching tabs...")
    new_window = [d for d in driver.window_handles if d != main_window][0]
    driver.switch_to_window(new_window)
    # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.TAB)

    wait(2)

    print("LOGGED IN!")
    print("======================================")

    return driver


def print_page_info(driver):
    print("Page Information:")
    print(" * Title:", driver.title)
    print(" * Url:", driver.current_url)
    print(" * Tab:", driver.current_window_handle,
          "(tab {}/{})".format(driver.window_handles.index(driver.current_window_handle) + 1,
                             len(driver.window_handles)))


def get_date_as_timestamp_str(date):
    if date is None:
        return str(None)
    elif type(date) is datetime.timedelta:
        h = int(int(date.seconds) / 3600)
        m = int((int(date.seconds) - h * 3600) / 60)
        s = int(int(date.seconds) - h * 3600 - m * 60)
        if date.days == 0:
            return "{:02d}:{:02d}:{:02d}".format(h, m, s)
        return "{:02d}.{:02d}:{:02d}:{:02d}".format(date.days, h, m, s)    
    return "{:02d}.{:02d}:{:02d}:{:02d} ({} ago)".format(date.day, date.hour, date.minute, date.second,
                                                         get_date_as_timestamp_str(datetime.datetime.now() - date))


def go_to_url(driver, url):
    driver.get(url)


def scroll_down(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")


def start_browser():
    return webdriver.Chrome()


def input_with_timeout(timeout=5, default="", wait_on_type=True):
    start_time = time.time()
    input = ""
    while True:
        if msvcrt.kbhit():
            byte_arr = msvcrt.getche()
            if ord(byte_arr) == 13:  # ENTER key
                break
            elif ord(byte_arr) == 8:  # BACKSPACE key
                input = input[:-1]
            elif ord(byte_arr) >= 32:  # SPACE key
                input += "".join(map(chr, byte_arr))
        if (len(input) == 0 or not wait_on_type) and (time.time() - start_time) > timeout:
            break

    if len(input) > 0:
        print("")  # move to next line
        return input
    else:
        return default


def wait_and_attack(planet_num, minutes_to_wait=60, resource="C", number_attacks=20, number_systems_to_spy=30):
    minutes_left = minutes_to_wait
    print("Instructions:")
    print("  1. Press ENTER to skip the current minute")
    print("  2. Press Q + ENTER (or Q and wait for minute to end) to start attack immediately")
    print("  3. Press P + NUMBER(s) + ENTER to change the planet attacking")
    print("  4. Press R + R/M/C/D + ENTER to change the resource to prioritize")
    print("  5. Press M + NUMBER(s) + ENTER to change the minutes left")
    print("  6. Press [+] or [-] + ENTER to increase/decrease minutes left by 5")
    while minutes_left > 0:
        print("{} minutes to attack from planet {} (Resource: {})...".format(minutes_left, planet_num, resource))
        out = input_with_timeout(timeout=60, wait_on_type=False).lower()
        firstchar = out[0] if len(out) > 0 else ""
        if firstchar == "q":
            break
        elif firstchar == "p":
            try:
                tmp = int(out[1:])
                planet_num = tmp
            except ValueError:
                print("Invalid number '{}'".format(out[1:]))
        elif firstchar == "m":
            try:
                tmp = int(out[1:])
                minutes_left = tmp
            except ValueError:
                print("Invalid number '{}'".format(out[1:]))
        elif firstchar == "+":
            minutes_left += 5
        elif firstchar == "-":
            minutes_left -= 5
        elif firstchar == "r":
            tmp = out[1].upper() if len(out) >= 2 else ""
            if tmp in ["R", "M", "C", "D"]:
                resource = tmp
            else:
                print("Invalid resource '{}'".format(tmp))
        if len(out) == 0:
            minutes_left -= 1
    print("Starting attack from planet {} (Resource: {})...".format(planet_num, resource))
    start_time = time.time()
    
    # start browser with game
    retries = 0
    while True:
        try:
            driver = login()

            # check login successful
            print_page_info(driver)
            assert driver.current_url.startswith(URL)

            # start bot
            game = OGame(driver)
            break
        except Exception:
            retries += 1
            if retries >= 3:
                raise Exception("Failed too many times!")
            print("Failure. Retrying...")
            wait(3)
            
    # attack
    try:
        game.spy_and_attack_best(planet_num, number_attacks, number_systems_to_spy, resource=resource)
    except Exception as e:
        print("Exception", e)
    print("Finished attack from planet {}!".format(planet_num))
    print("Time taken: {:0.2f} minutes!".format((time.time() - start_time) / 60))
    return planet_num, resource


if __name__ == "__main__":
    # login
    # driver = login()

    # check login successful
    # print_page_info(driver)
    # assert driver.current_url.startswith(URL)

    # start bot
    # game = OGame(driver)

    # game.spy_and_attack_best(1, 8, number_systems_to_spy=30, skip_middle=None, resource="R")

    # game.spy_around_and_read_messages(planet_index=0, number_systems=30)
    # game.msgs.attack_number(1)

    # game.planets[0].spy_close_inactive_planets(50)

    # msgs = MessagePanel(driver)
    # msgs.get_messages()

    wait_minutes = 42  # average minutes to wait
    wait_minutes_dev = 3  # +- deviation to wait
    planets_to_attack_from = [0, 1, 2, 3, 4, 5]
    i = 0
    resource = "R"
    while True:
        random_wait = wait_minutes + random.randint(-wait_minutes_dev, wait_minutes_dev)
        planet_num = planets_to_attack_from[i]
        new_planet_num, resource = wait_and_attack(planet_num,
                                                   minutes_to_wait=random_wait,
                                                   resource=resource,
                                                   number_attacks=20,
                                                   number_systems_to_spy=30)
        try:
            new_i = planets_to_attack_from.index(new_planet_num)
        except ValueError:
            new_i = i
        i = (new_i + 1) % len(planets_to_attack_from)

