from raid_planets import *


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

email = None
password = None


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
        self.refresh_fields()

    def refresh_fields(self):
        self.planet_number = int(self.planet_tr.find_element_by_class_name("position").get_attribute("innerHTML"))
        self.planet_name = self.planet_tr.find_element_by_class_name("planetname").get_attribute("innerHTML").strip()
        self.player = self.planet_tr.find_element_by_class_name("playername").find_element_by_tag_name("a").\
            find_element_by_tag_name("span").get_attribute("innerHTML").strip()
        self.filter = self.planet_tr.get_attribute("class")
        self.refresh()

    def update(self):
        self.get_planet_tr()
        self.refresh_fields()

    def spy(self, only_if_never_spied=True, retry=3):
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
                if self.verbose:
                    print("Spied successfully: {}".format(self))
            elif retry > 0:
                random_wait = 0 if not self.randomize_wait else random.random() * 2 - 1
                wait(self.wait_long + random_wait)
                self.spy(only_if_never_spied=only_if_never_spied, retry=retry - 1)
            elif self.verbose:
                print("Could not spy: {}".format(self))
        elif self.verbose:
            print("Already spied before: {}".format(self))

    def get_planet_tr(self):
        self.get_current_galaxy_and_system()
        if self.galaxy_number != self.current_galaxy_num or self.system_number != self.current_system_num:
            self.go_to_galaxy_and_system(self.galaxy_number, self.system_number)
        planets_tr = self.driver.find_element_by_id("galaxytable").find_element_by_tag_name("tbody").find_elements_by_tag_name("tr")
        found = False
        for p in planets_tr:
            if p.find_element_by_class_name("position").get_attribute("innerHTML") == str(self.planet_number):
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
        while self.current_system_num <= last_system:
            planets_spied += self.spy_current_system(filters=filters)
            random_wait = 0 if not self.randomize_wait else random.random() - 0.5
            wait(self.wait_short + random_wait)
            self.move("R")
        return planets_spied

    def spy_current_system(self, filters=["inactive"]):
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
            self.planets[pos].spy()
        self.refresh()
        return len(new_planets)
    
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
            print("This planet may have defense! --------------------------------------------------------------------------------")
            return True
        return self.defense > 0 or self.fleet > 0

    def get_num_cargos(self, storage=37500, resources_percentage=50):
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

    def attack_number(self, number, send_fleet=False, ignore_if_defended=True):
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
        cargos = panel.get_technology("transporterLarge")
        if cargos.level == 0:
            print("No cargos available")
            raise Exception("No cargos available")
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
                return False
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
            if self.verbose:
                print("Attacked!\n")
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

    def get_messages(self, erase_message=False):
        try:
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
        except Exception:
            self.open_messages()
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
        i = -1
        while len(messages) > 0:
            msg = messages[0]
            messages = self.driver.find_element_by_id("fleetsgenericpage").find_elements_by_class_name("msg")
            i += 1
            msg_id = msg.get_attribute("data-msg-id")
            if self.verbose:
                print("Reading message {} with message id {}".format(i + 1, msg_id))
            if msg_id in self.message_ids:
                continue
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
                    continue
                try:
                    resources = spans[0].find_elements_by_class_name("resspan")
                    m = int(resources[0].get_attribute("innerHTML").split("Metal: ")[1].replace(".", "").replace(",", ""))
                    c = int(resources[1].get_attribute("innerHTML").split("Cristal: ")[1].replace(".", "").replace(",", ""))
                    d = int(resources[2].get_attribute("innerHTML").split("Deuterio: ")[1].replace(".", "").replace(",", ""))
                except Exception:
                    continue
            defense, fleet = None, None
            for line in lines:
                spans = line.find_elements_by_class_name("ctn")
                if len(spans) != 2:
                    continue
                if "tooltipLeft" not in spans[0].get_attribute("class") or "tooltipRight" not in spans[1].get_attribute("class"):
                    continue
                try:
                    fleet = int(spans[0].get_attribute("innerHTML").split("Flotas: ")[1].replace(".", "").replace(",", ""))
                    defense = int(spans[1].get_attribute("innerHTML").split("Defensa: ")[1].replace(".", "").replace(",", ""))
                except Exception as e:
                    continue
            attack_href = msg.find_element_by_class_name("msg_actions").find_element_by_class_name("icon_attack").find_element_by_xpath("./..").get_attribute("href")
            self.message_ids.add(msg_id)  # never read same message twice
            if d is not None:
                self.messages[msg_id] = Message(self.driver, msg_time, msg_id, len(self.messages), name_and_coords, coords, m, c, d, defense, fleet, attack_href, verbose=self.verbose)
                res = m + c + d
                for res, res_key in zip((m, c, d, m + c + d), ("M", "C", "D", "R")):
                    if res not in self.resources[res_key]:
                        self.resources[res_key][res] = []
                    self.resources[res_key][res].append(msg_id)
            if erase_message:
                try:
                    msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a").click()
                except Exception:
                    try:
                        self.driver.find_element_by_class_name("tpd-content").find_element_by_class_name("close-tooltip").click()  # close tooltip
                    except Exception:
                        pass
                    tmp = msg.find_element_by_class_name("msg_head").find_element_by_class_name("fright").find_element_by_tag_name("a")
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", tmp)
                    except Exception:
                        pass
                    tmp.click()

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

    def get_all_messages(self):
        self.get_page_number()
        for _ in range(self.num_pages):
            self.get_messages(erase_message=True)
            self.open_messages()


class PlanetsSimple(Refreshable):

    def __init__(self, driver, planets_ids, verbose=True, wait_short=1, randomize_wait=True):
        self.driver = driver
        self.ids = planets_ids
        self.id = self.ids[0]
        self.verbose = verbose
        self.wait_short = wait_short  # seconds
        self.randomize_wait = randomize_wait

    def spy_close_inactive_planets(self, planet_index, number_systems=10, skip_middle=None):
        self.id = self.ids[planet_index]
        self.click_planet_if_not_current()
        self._get_planet_info()
        # make sure enough probes and cargos
        self._go_to_tab(8)  # Hangar
        panel = Panel(self.driver, tab=8, verbose=False)
        if panel.get_technology("espionageProbe").level < 10:
            raise Exception("Build more probes to spy efficiently")
        if panel.get_technology("transporterLarge").level <= 5:
            raise Exception("Build more cargos to attack efficiently")
        # go to galaxy and spy
        self._go_to_tab(9)  # Galaxia
        self.galaxy = GalaxyPanel(self.driver)
        planets_spied = self.galaxy.spy_around(number_systems, skip_middle=skip_middle)
        if self.verbose:
            print("Planets Spied:", planets_spied, "\n")
    
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

    def _is_planet_highlighted(self):
        return "hightlightPlanet" in self._planet_div().get_attribute("class")

    def _planet_str(self):
        return "{} {}".format(self.name, self.coords_str)

    def _click_planet(self):
        self._planet_div().click()
        self.refresh()
        if self.verbose:
            print ("Clicking on Planet: {}{}".format(self._planet_str(), " - Opening in new tab" if with_ctrl else ""))

    def _go_to_tab(self, tab):
        url = URL + "&component={}"
        go_to_url(self.driver, url.format(TABS[tab]))
        self.refresh()
        if self.verbose:
            print ("Clicking on Tab: {} ({})".format(TABS[tab], tab))

    def _planet_div(self):
        return self.driver.find_element_by_id(self.id)


class OGameSimple(object):

    def __init__(self, driver, verbose=True, wait_long=3, wait_short=1):
        # variables from input variables
        self.driver = driver
        self.verbose = verbose
        self.wait_long = wait_long
        self.wait_short = wait_short

        self._get_planets()
        self._initialize_planet()

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

    def _initialize_planet(self):
        self.planets = PlanetsSimple(self.driver, self.planets_ids,
                                     verbose=self.verbose, wait_short=self.wait_short)

    def spy_close_inactive_planets(self, planet_index, number_systems=30, skip_middle=None):
        self.planets.spy_close_inactive_planets(planet_index, number_systems, skip_middle)
    
    def read_all_spionage_messages(self, restart=True):
        if restart:
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
        wait(5)
        try:
            self.read_all_spionage_messages()
        except Exception:
            print("There was an error reading messages, trying again...")
            self.read_all_spionage_messages(restart=False)

    def spy_and_attack_best(self, planet_index, number_attacks, number_systems_to_spy=None, resource="R", skip_middle=None, erase_messages_before=True):
        if number_systems_to_spy is not None:
            self.spy_around_and_read_messages(planet_index, number_systems_to_spy, skip_middle=skip_middle, erase_messages_before=erase_messages_before)
        if self.verbose:
            print("Attacking...")
        for i in range(number_attacks):
            print("Attack #{}".format(i + 1))
            msg = self.msgs.get_first_not_attacked_message(resource=resource)
            self.msgs.attack_number(msg.msg_number, send_fleet=True)
            wait(3)


if __name__ == "__main__":
    # login
    driver = login()
    game = OGameSimple(driver)

    # start bot

    game.spy_and_attack_best(1, 8, number_systems_to_spy=30, skip_middle=None, resource="R")
