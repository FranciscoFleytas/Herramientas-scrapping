import time
import os
import json
import random
import google.generativeai as genai
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, ElementNotInteractableException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import argparse
import sys

# ==========================================
# CONFIGURACION
# ==========================================
TARGET_URL = "https://www.instagram.com/p/DSz7ev-DTYr/" # TU LINK DE REEL
GEMINI_API_KEY = "AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g"
CUENTAS_FILE = 'cuentas.json'
ENABLE_SAVE = False  # Cambiar a True si quieres guardar/bookmark la publicación

class TestBot:
    def __init__(self):
        print("[INIT] Iniciando Motor de Pruebas (V15 - Anti-Comentarios)...")
        self.account = self.load_account()
        if not self.account: raise Exception("[ERROR] Falta cuentas.json")

        options = uc.ChromeOptions()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")
        
        self.driver = uc.Chrome(options=options, version_main=142)
        self.wait = WebDriverWait(self.driver, 10)
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        # flags set per-run
        self.dump_html_on_fail = False
        self.enable_save_flag = False

    def load_account(self):
        if not os.path.exists(CUENTAS_FILE): return None
        try:
            with open(CUENTAS_FILE, 'r') as f:
                data = json.load(f)
                return data[0] if data else None
        except: return None

    def login_and_go(self):
        print(f"[LOGIN] Usuario: {self.account.get('user')}")
        self.driver.get("https://www.instagram.com/404")
        time.sleep(1) 
        self.driver.add_cookie({
            'name': 'sessionid', 'value': self.account['sessionid'],
            'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True
        })
        
        print(f"[NAV] Yendo a: {TARGET_URL}")
        self.driver.get(TARGET_URL)
        time.sleep(5) 
        self.dismiss_popups()
        
        if "accounts/login" in self.driver.current_url:
            print("[ERROR] Redireccion al login detectada.")
            return False
        return True

    def dismiss_popups(self):
        try:
            xpath = "//button[text()='Ahora no' or text()='Not Now']"
            btn = self.driver.find_element(By.XPATH, xpath)
            btn.click()
        except: pass

    # ==============================================================================
    # 🕵️ INSPECTOR MEJORADO
    # ==============================================================================
    def debug_inspector(self):
        print("\n" + "="*50)
        print("[INSPECTOR] Analizando estructura HTML...")
        print("="*50)
        
        container = None
        # Prioridad 1: Article (Post normal)
        articles = self.driver.find_elements(By.TAG_NAME, "article")
        if articles: 
            print("[INFO] Detectado <article> (Post Estandar)")
            container = articles[0]
        else:
            # Prioridad 2: Main (Reels / Video Fullscreen)
            mains = self.driver.find_elements(By.TAG_NAME, "main")
            if mains:
                print("[INFO] Detectado <main> (Posible Reel/Video)")
                container = mains[0]
            else:
                print("[WARN] No se detecto contenedor estandar. Usando body.")
                container = self.driver.find_element(By.TAG_NAME, "body")

        # Buscar Botones de Like especificamente
        print("\n🔍 --- BUSCANDO BOTON 'ME GUSTA' ---")
        targets = ["Me gusta", "Like", "Deshacer", "Unlike"]
        conds = " or ".join([f"@aria-label='{l}'" for l in targets])
        xpath_btn = f".//*[local-name()='svg' and ({conds})]"
        
        found_svgs = container.find_elements(By.XPATH, xpath_btn)
        if not found_svgs:
            # Busqueda Global si falla la local
            found_svgs = self.driver.find_elements(By.XPATH, f"//*[local-name()='svg' and ({conds})]")

        for i, svg in enumerate(found_svgs):
            label = svg.get_attribute("aria-label")
            try:
                # Chequeo si esta dentro de una lista (es un comentario)
                is_comment = svg.find_elements(By.XPATH, "./ancestor::ul")
                tipo = "COMENTARIO (Ignorar)" if is_comment else "BOTON PRINCIPAL"
            except: tipo = "?"

            print(f"   [{i}] Icono: '{label}' | Tipo: {tipo} | Visible: {svg.is_displayed()}")

    # ==============================================================================
    # 🛠️ CLIC MAESTRO (ActionChains)
    # ==============================================================================
    def smart_click(self, element):
        """Intenta click normal, si falla usa Mouse real (ActionChains)"""
        # Metodo 1: Mouse Over + Click (lo más humano)
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element(element).pause(0.2).click().perform()
            return True
        except Exception as e:
            print(f"   [DEBUG] smart_click: actionchains failed: {e}")
        # Metodo 2: Click nativo
        try:
            element.click()
            return True
        except Exception as e:
            print(f"   [DEBUG] smart_click: element.click() failed: {e}")
        # Metodo 3: JS Force
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            print(f"   [DEBUG] smart_click: js click failed: {e}")
        return False

    def fallback_click_methods(self, element):
        """Try aggressive fallbacks: click svg child, dispatch mouse events at center, click by coordinates."""
        # 1) click child svg
        try:
            svg = element.find_element(By.XPATH, './/svg')
            try:
                svg.click()
                return True
            except:
                self.driver.execute_script("arguments[0].click();", svg)
                return True
        except:
            pass

        # 2) dispatch mouse events at center via JS
        try:
            rect = self.driver.execute_script(
                "var r=arguments[0].getBoundingClientRect(); return {x:r.left, y:r.top, w:r.width, h:r.height};",
                element
            )
            cx = int(rect['x'] + rect['w']/2)
            cy = int(rect['y'] + rect['h']/2)
            dispatch = (
                "var ev = new MouseEvent('click', {bubbles:true, cancelable:true, view:window,"
                f" clientX:{cx}, clientY:{cy}); arguments[0].dispatchEvent(ev);"
            )
            self.driver.execute_script(dispatch, element)
            return True
        except Exception as e:
            print(f"   [DEBUG] fallback_click_methods: dispatch failed: {e}")

        # 3) try ActionChains click at offset (best-effort)
        try:
            loc = element.location_once_scrolled_into_view
            size = element.size
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(element, size['width']/2, size['height']/2).click().perform()
            return True
        except Exception as e:
            print(f"   [DEBUG] fallback_click_methods: move_to_offset failed: {e}")

        return False

    def human_type_robust(self, xpath, text):
        print(f"   [TYPE] Escribiendo: '{text}'")
        try:
            element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.smart_click(element)
        except: pass

        for char in text:
            try:
                element.send_keys(char)
            except:
                try:
                    element = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    element.send_keys(char)
                except: break
            time.sleep(random.uniform(0.02, 0.07))

    # ==============================================================================
    # ⚡ TEST LIKE (CON FILTRO ANTI-COMENTARIOS)
    # ==============================================================================
    def test_like(self):
        print("\n[TEST] Probando LIKE...")
        target_labels = ["Me gusta", "Like"]
        conditions = " or ".join([f"@aria-label='{label}'" for label in target_labels])

        # Buscamos candidatos dentro del contenedor principal (article o main)
        container = None
        articles = self.driver.find_elements(By.TAG_NAME, 'article')
        if articles:
            container = articles[0]
        else:
            mains = self.driver.find_elements(By.TAG_NAME, 'main')
            container = mains[0] if mains else self.driver.find_element(By.TAG_NAME, 'body')

        xpath_candidates = f".//button[.//svg[({conditions})]] | .//div[@role='button'][.//svg[({conditions})]] | .//a[.//svg[({conditions})]]"

        try:
            candidates = container.find_elements(By.XPATH, xpath_candidates)
        except:
            candidates = []

        candidate_htmls = []
        # If no candidates found as buttons/links/divs, fall back to raw SVGs (debug_inspector finds these)
        if not candidates:
            try:
                svgs = container.find_elements(By.XPATH, f".//*[local-name()='svg' and ({conditions})]")
            except:
                svgs = []

            for sidx, svg in enumerate(svgs):
                try:
                    # try to find a clickable ancestor for the svg
                    try:
                        cand = svg.find_element(By.XPATH, './ancestor::button | ./ancestor::a | ./ancestor::div[@role="button"]')
                    except:
                        # fallback to parent
                        try:
                            cand = svg.find_element(By.XPATH, './..')
                        except:
                            cand = svg

                    # ensure we collected outerHTML for debugging
                    try:
                        candidate_htmls.append(cand.get_attribute('outerHTML') or svg.get_attribute('outerHTML') or '')
                    except:
                        candidate_htmls.append('')

                    # skip if inside comments/dialog
                    skip = False
                    ancestor = cand
                    while True:
                        try:
                            ancestor = ancestor.find_element(By.XPATH, './..')
                        except:
                            break
                        tag = ancestor.tag_name.lower()
                        role = ancestor.get_attribute('role') or ''
                        cls = ancestor.get_attribute('class') or ''
                        if tag == 'ul' or role == 'dialog' or 'comment' in cls.lower() or 'comments' in cls.lower():
                            skip = True
                            break

                    if skip:
                        continue

                    if not cand.is_displayed():
                        continue

                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cand)
                        time.sleep(0.25)
                    except:
                        pass

                    clicked = False
                    try:
                        clicked = self.smart_click(cand)
                    except Exception:
                        clicked = False

                    if not clicked:
                        try:
                            if self.fallback_click_methods(cand):
                                clicked = True
                        except Exception:
                            clicked = False

                    if clicked:
                        aria = ''
                        try:
                            aria = svg.get_attribute('aria-label') or cand.get_attribute('aria-label')
                        except:
                            aria = ''
                        print(f"   [OK] Click realizado en svg-candidato #{sidx} (aria-label='{aria}')")
                        return True
                except Exception as e:
                    print(f"   [DEBUG] svg-candidate #{sidx} error: {e}")
                    continue
        for idx, cand in enumerate(candidates):
            try:
                # Saltar botones dentro de listas de comentarios o diálogos (comment scroller)
                skip = False
                ancestor = cand
                while True:
                    try:
                        ancestor = ancestor.find_element(By.XPATH, './..')
                    except:
                        break
                    tag = ancestor.tag_name.lower()
                    role = ancestor.get_attribute('role') or ''
                    cls = ancestor.get_attribute('class') or ''
                    if tag == 'ul' or role == 'dialog' or 'comment' in cls.lower() or 'comments' in cls.lower():
                        skip = True
                        break

                if skip:
                    continue

                if not cand.is_displayed():
                    continue

                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cand)
                    time.sleep(0.35)
                except:
                    pass

                clicked = False
                try:
                    clicked = self.smart_click(cand)
                except Exception as e:
                    print(f"   [DEBUG] smart_click raised: {e}")

                if not clicked:
                    # try fallbacks
                    try:
                        if self.fallback_click_methods(cand):
                            clicked = True
                    except Exception as e:
                        print(f"   [DEBUG] fallback_click_methods raised: {e}")

                if clicked:
                    aria = ''
                    try:
                        aria = cand.find_element(By.XPATH, './/svg').get_attribute('aria-label')
                    except:
                        aria = cand.get_attribute('aria-label') or ''
                    print(f"   [OK] Click realizado en candidato #{idx} (aria-label='{aria}')")
                    return True

                try:
                    candidate_htmls.append(cand.get_attribute('outerHTML'))
                except:
                    candidate_htmls.append('')

            except (StaleElementReferenceException, ElementNotInteractableException, TimeoutException):
                continue
            except Exception as e:
                print(f"   [DEBUG] candidato #{idx} fallo: {e}")
                continue

        print("   [FAIL] No se pudo dar Like (¿Quizas ya tiene like o cambió el selector?).")
        if self.dump_html_on_fail:
            print("   [DEBUG] Dumping candidate HTMLs (truncated):")
            for i, h in enumerate(candidate_htmls):
                print(f"   --- Candidate #{i} outerHTML (start): {h[:1200]}\n")
        return {"ok": False, "candidates": candidate_htmls}

    def save_post(self):
        """Intenta hacer 'Guardar' (bookmark) en la publicación actual.
        Busca botones con aria-label 'Guardar'/'Save' y hace click en el ancestro clickeable.
        """
        save_labels = ["Guardar", "Save"]
        cond = " or ".join([f"contains(@aria-label, '{l}')" for l in save_labels])
        xpath_save = f"//*[local-name()='svg' and ({cond})]"

        try:
            svgs = self.driver.find_elements(By.XPATH, xpath_save)
        except:
            svgs = []

        for i, svg in enumerate(svgs):
            try:
                # prefer ancestor button/a/div role=button
                try:
                    clickable = svg.find_element(By.XPATH, './ancestor::button | ./ancestor::a | ./ancestor::div[@role="button"]')
                except:
                    clickable = svg

                if not clickable.is_displayed():
                    continue

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", clickable)
                time.sleep(0.3)
                if self.smart_click(clickable):
                    print(f"   [OK] Publicación guardada (candidate #{i}).")
                    return True
            except:
                continue

        print("   [WARN] No se encontró botón de guardar.")
        return False

    # ==============================================================================
    # ⚡ TEST COMMENT
    # ==============================================================================
    def test_comment(self):
        print("\n[TEST] Probando COMENTARIO...")
        text = "Awesome content!"
        
        xpath_target = "//textarea[@aria-label='Agrega un comentario...'] | //textarea[@aria-label='Add a comment…'] | //form//textarea"
        
        # 1. Buscar Caja
        try:
            self.wait.until(EC.presence_of_element_located((By.XPATH, xpath_target)))
        except:
            print("   [WARN] Caja no visible. Buscando burbuja...")
            try:
                # Burbuja de chat (Global scan para Reels)
                # Tambien protegemos esto de no clicar "Responder" en comentarios
                bubble_xpath = "//*[local-name()='svg' and (@aria-label='Comentar' or @aria-label='Comment') and not(ancestor::ul)]/.."
                bubble = self.driver.find_element(By.XPATH, bubble_xpath)
                self.smart_click(bubble)
                time.sleep(1)
            except:
                print("   [FAIL] No se pudo activar la caja.")
                return False

        self.human_type_robust(xpath_target, text)
        print("   [OK] Escritura finalizada.")
        return True

    def run(self):
        # Backwards-compatible: run with global TARGET_URL
        return self.run_url(TARGET_URL, enable_save=ENABLE_SAVE, dump_html_on_fail=False)

    def run_url(self, url, enable_save=False, dump_html_on_fail=False):
        """Run the sequence (login,navigate,like,comment,optional save) for a single URL.
        Returns a dict with results.
        """
        self.dump_html_on_fail = dump_html_on_fail
        self.enable_save_flag = enable_save
        result = {"url": url, "liked": False, "commented": False, "saved": False, "error": None}

        try:
            # login + navigate
            print(f"[LOGIN] Usuario: {self.account.get('user')}")
            self.driver.get("https://www.instagram.com/404")
            time.sleep(1)
            self.driver.add_cookie({
                'name': 'sessionid', 'value': self.account['sessionid'],
                'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True
            })

            print(f"[NAV] Yendo a: {url}")
            self.driver.get(url)
            time.sleep(5)
            self.dismiss_popups()

            if "accounts/login" in self.driver.current_url:
                result['error'] = 'Redirected to login'
                return result

            self.debug_inspector()

            liked_res = self.test_like()
            # test_like now returns dict on failure or True on success
            if isinstance(liked_res, dict):
                result['liked'] = False
                result['candidates_html'] = liked_res.get('candidates', [])
            else:
                result['liked'] = bool(liked_res)

            commented = False
            try:
                commented = self.test_comment()
            except Exception as e:
                print(f"[WARN] Comment failed: {e}")
            result['commented'] = bool(commented)

            if enable_save:
                saved = self.save_post()
                result['saved'] = bool(saved)

            print("\n[FIN] Run for URL finished.\n")
            return result

        except Exception as e:
            result['error'] = str(e)
            print(f"[ERROR GENERAL] {e}")
            return result
        finally:
            # keep browser open for subsequent runs (runner will quit)
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TestBot runner CLI')
    parser.add_argument('--url', help='URL to run against', default=None)
    parser.add_argument('--enable-save', action='store_true', help='Attempt to save/bookmark the post')
    parser.add_argument('--dump-html-on-fail', action='store_true', help='Dump candidate outerHTML when like fails')
    args = parser.parse_args()

    bot = TestBot()
    if args.url:
        res = bot.run_url(args.url, enable_save=args.enable_save, dump_html_on_fail=args.dump_html_on_fail)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        # Quit driver and exit
        bot.driver.quit()
        sys.exit(0 if not res.get('error') else 2)
    else:
        try:
            bot.run()
        finally:
            bot.driver.quit()