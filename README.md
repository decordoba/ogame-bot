# ogame-bot

Simple ogame bot to attack inactive planets.

This bot uses selenium to attack all inactive planets close to each of the available planets.

### Warning:

*This code is given as-is and with no guarantees. The code is dirty, overly complicated, and has a lot of functions/options that have no purpose anymore. I built this for my needs only, and I never got around cleaning it. There are plenty of utilities buried in the code, but the useful part is only a fraction of the file.*

*Also, last time the code was testes to check it worked was on 27/08/2020, so if you are reading this far into the future, maybe the ogame website has changed and this code has to be adapted to make this work again. Who know!*

*Also, this code has been tested in the Spanish Ogame only, so a few of the strings used may need to be changed for other languages. See adapt to your own language section to find fields that you may want to change.*

## Requirements

1. Python 3.5 or greater
2. selenium package: `pip install selenium`
3. lxml package: `pip install lxml`

## How it works

### How to run it

Run the `raid_planets.py` file:

```python raid_planets.py```

### The menu

After running, you will see the next dialog:

```
Instructions:
  1. Press ENTER to skip the current minute
  2. Press Q + ENTER (or Q and wait for minute to end) to start attack immediately
  3. Press P + NUMBER(s) + ENTER to change the planet attacking
  4. Press R + R/M/C/D + ENTER to change the resource to prioritize
  5. Press M + NUMBER(s) + ENTER to change the minutes left
  6. Press [+] or [-] + ENTER to increase/decrease minutes left by 5
42 minutes to attack from planet 0 (Resource: R)...
41 minutes to attack from planet 0 (Resource: R)...
...
```

This is the navigation menu, to select when and where to attack from. The code is quite dumb and pretty random, and it will wait approximately 42 minutes (because 42 is the answer to everything) between each attack. You may want to configure the waits in the code depending on your universe and the speed of your ships, but this time is chosen as a rough estimate of the time that ships will take to attack and come back from close planets.

To skip the wait and start the attack press Q + ENTER.

To choose the planet to attack from, press Pn + ENTER (where n is a number from 0 to 9) to select the planet index. This refers to the order of your planets, where 0 is the 1st and 9 is the 10th.

To select a resource to maximize, use Px + ENTER (where x is resource type: R(resource), M(metal), C(crystal), D(deuterium)). Attacks are done in order, prioritizing attacks on planets with more ot the chosen resource.

Mn + ENTER (where n is the number of minutes left) will change the number of minutes left to start the attack. Also + and - followed by ENTER can be used to increse or decreate the remaining time by 5 minutes.

### The login process

Go ahead and press Q + ENTER if you haven't already. This will start the attack. You will get a prompt to ask for credentials. You can save creds in the file too (by filling constants EMAIL and PASSWORD) to skip this step.

```
Starting attack from planet 0 (Resource: R)...
======================================
LOGGING IN...
No email/username provided. Please type your email to log into the game.
>> myemail@gmail.comm
No password provided. Please type your password to log into the game.
>> mypassword
```

Fill the credentials that you use to access ogame. A new Chrome window will open and start ogame. This is the first and only place where you will have to go to the code and change things if you are not using the Spanish ogame: the url, and the text in the log in and continue playing buttons. Check section 'Adapt to your own language' to find out what lines to change.

If everything went well, you should see the main ogame screen. Now, it will start iterating all your planets (and clicking them). This is useless for what we will do later, but I never changed it.

### The attack

After the last planet has been clicked, the phases of the attack will begin. There are plenty of random waits between the phases, so be patient:
1. The message tab is clicked and all spionage message are erased.
2. Galaxy tab is clicked. Up to 30 systems will be checked around your system (15 to the left, 14 to the right and the current one) and all inactive planets will be spied with one probe (you need at least 5 probes in the planet or the planet attack will be skipped)
3. Check all messages, order them by resource, and attack all the planets that have no defense in that order. If defense is unknown, it will not attack them unless coordinates are saved to constant PLANETS_WITH_NO_DEFENSE. All attacks will be done with large cargos, and you need at least 10 before attacking or your planet will not attack anywhere. Also, the cargo number is calculated depending on the planet resources and the constant STORAGE_LARGE_CARGO.
4. Every spionage message will be erased, including those that are not the result of spying another planet (for example, another player spying us).
5. If we run out of cargos or we reach 20 attacks or something fails, the attack will end.

After the attack ends, the menu will be shown again and after 42ish minutes, the next attack will start (for the next planet).

## Contrinuting to this code

I doubt it will ever happen, but if someone wanted to clean this mess up, I would be happy to take PRs. Also, feel free to fork this repo and do your own stuff, I am going to be done with ogame soon (also, attacking inactive users stops making sense once the universe is a bit old).

## Adapt to your own language

These are a few of the thing that I have hardcoded for Spanish. Change them to fit your language ogame version:
```
# choose your own URLs
LOGIN_URL = "https://lobby.ogame.gameforge.com/es_ES/?language=es"
URL = "https://s168-es.ogame.gameforge.com/game/index.php?page=ingame"
# choose the tab that has to be clicked to log in (default tab is sign up)
text = tabs.find_elements_by_xpath("//*[contains(text(), 'Iniciar sesión')]")[0]
# choose some unique text in the last played (gray) button in the screen after the login screen
text = driver.find_elements_by_xpath("//*[contains(text(), 'Jugado por última vez')]")[0]
# this is not required; this is the text for current production on hover over resources
self.production = int(tooltip.split("<th>Producción actual:</th>")[1].split("<span")[1].split(">")[1].split("<")[0].replace(".", "").replace(",", ""))
```

## Troubleshooting

If you see an error similar to the following:
`SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 80`, it means you need to update chromedriver.exe.

Follow this to do so: https://sites.google.com/a/chromium.org/chromedriver/downloads/version-selection

Also, this has only been tested in my computer which has a large screen. For smaller monitors, the website will be resized, and selenium may not be able to click on elements that are hidden unless it scrolls. If you find errors that indicate that an element is not clickable, `self.driver.execute_script("arguments[0].scrollIntoView();", element)` should be useful to show that element on screen.