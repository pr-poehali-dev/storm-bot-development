import { useState, useEffect, useCallback } from "react";
import Icon from "@/components/ui/icon";

/* ─────────── ДАННЫЕ ─────────── */
const CARS = [
  { id: 1,  name: "Доминатор",   emoji: "🚗", price: 5000,  desc: "Надёжный перехватчик первого уровня" },
  { id: 2,  name: "Циклон",      emoji: "🚙", price: 8000,  desc: "Усиленный кузов, мощные тормоза" },
  { id: 3,  name: "Ураган",      emoji: "🚐", price: 12000, desc: "Бронированные стёкла, высокий клиренс" },
  { id: 4,  name: "Титан",       emoji: "🛻", price: 16000, desc: "Полноприводный монстр с лебёдкой" },
  { id: 5,  name: "Вихрь",       emoji: "🚓", price: 21000, desc: "Спортивные шины, аэродинамический обвес" },
  { id: 6,  name: "Смерч",       emoji: "🚕", price: 26000, desc: "Турбодвигатель 600 л.с., клетка безопасности" },
  { id: 7,  name: "Тайфун",      emoji: "🚌", price: 31000, desc: "Мощный внедорожник с дополнительными баками" },
  { id: 8,  name: "Гроза",       emoji: "🏎️", price: 37000, desc: "Гоночный перехватчик EF5-класса" },
  { id: 9,  name: "Немезида",    emoji: "🚑", price: 43000, desc: "Самовосстанавливающийся корпус" },
  { id: 10, name: "Армагеддон",  emoji: "🚀", price: 50000, desc: "Легендарный перехватчик — вершина технологий" },
];

const EF_DATA: Record<number, { name: string; wind: string; efClass: string; chance: number; reward: number }> = {
  1: { name: "EF1", wind: "135–174 км/ч", efClass: "ef1", chance: 80, reward: 300 },
  2: { name: "EF2", wind: "175–217 км/ч", efClass: "ef2", chance: 65, reward: 600 },
  3: { name: "EF3", wind: "218–265 км/ч", efClass: "ef3", chance: 50, reward: 1100 },
  4: { name: "EF4", wind: "266–322 км/ч", efClass: "ef4", chance: 35, reward: 2000 },
  5: { name: "EF5", wind: "322+ км/ч",    efClass: "ef5", chance: 20, reward: 4000 },
};

const BOOST_COOLDOWN = 20 * 60 * 1000;

type Tab = "profile" | "shop" | "storm";
type StormPhase = "select" | "waiting" | "result";

interface OwnedCar {
  id: number;
  level: number;
  broken: boolean;
}

interface StormResult {
  ef: number;
  success: boolean;
  broken: boolean;
  reward: number;
  message: string;
}

/* ─────────── ASCII АРТ ─────────── */
const ASCII_TORNADO = `   (  )  )
  (  (  )
   )  )  (
  (  (    )
 ──────────────
    ~ШТОРМ~`;

const ASCII_CAR = `  ______
 /|_||_\\'.__)
(   _    _ _\\
=\`-(_)--(_)-'`;

const ASCII_SUCCESS = ` ✦ ★ ✦ ★ ✦
█ ПЕРЕХВАТ █
 ✦ ★ ✦ ★ ✦`;

const ASCII_FAIL = ` ✖ ✖ ✖ ✖ ✖
█  ПРОВАЛ  █
 ✖ ✖ ✖ ✖ ✖`;

/* ─────────── ВЕРХНЯЯ ПАНЕЛЬ ─────────── */
function TopBar({ tab, setTab, balance }: { tab: Tab; setTab: (t: Tab) => void; balance: number }) {
  return (
    <div className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b border-border">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl animate-flicker">🌪️</span>
          <span className="font-storm text-xl tracking-widest text-storm-yellow" style={{ letterSpacing: "0.2em" }}>
            ШТОРМ
          </span>
        </div>
        <div className="flex items-center gap-1 px-3 py-1 rounded border border-storm-yellow/30 bg-storm-yellow/5">
          <span className="font-mono-storm text-storm-yellow text-sm font-bold">{balance.toLocaleString()}</span>
          <span className="text-xs text-muted-foreground ml-1">МШ</span>
        </div>
      </div>
      <div className="max-w-2xl mx-auto px-4 pb-2 flex gap-1">
        {(["profile", "shop", "storm"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-storm tracking-wider transition-all duration-200 rounded border
              ${tab === t
                ? "border-storm-yellow text-storm-yellow bg-storm-yellow/10 glow-yellow"
                : "border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground"
              }`}
          >
            {t === "profile" ? "⚡ ПРОФИЛЬ" : t === "shop" ? "🔧 МАГАЗИН" : "🌪️ ОХОТА"}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ─────────── ПРОФИЛЬ ─────────── */
function ProfileTab({
  balance, setBalance, name, setName,
  ownedCars, setOwnedCars,
  lastBoost, setLastBoost,
}: {
  balance: number; setBalance: (b: number) => void;
  name: string; setName: (n: string) => void;
  ownedCars: OwnedCar[]; setOwnedCars: (c: OwnedCar[]) => void;
  lastBoost: number; setLastBoost: (t: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState(name);
  const [boostTimer, setBoostTimer] = useState(0);
  const [boostEffect, setBoostEffect] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = Math.max(0, BOOST_COOLDOWN - (Date.now() - lastBoost));
      setBoostTimer(remaining);
    }, 1000);
    return () => clearInterval(interval);
  }, [lastBoost]);

  const canBoost = boostTimer === 0;

  const handleBoost = () => {
    if (!canBoost) return;
    const now = Date.now();
    setBalance(balance + 200);
    setLastBoost(now);
    saveBoostTime(now);
    setBoostEffect(true);
    setTimeout(() => setBoostEffect(false), 600);
  };

  const removeCar = (carId: number) => {
    setOwnedCars(ownedCars.filter((c) => c.id !== carId));
  };

  const formatTimer = (ms: number) => {
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const levelColors: Record<number, string> = { 1: "text-storm-green", 2: "text-storm-cyan", 3: "text-storm-yellow" };

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Шапка профиля */}
      <div className="card-storm rounded p-5 relative overflow-hidden">
        <div className="absolute top-2 right-4 opacity-10 text-8xl select-none pointer-events-none">🌪️</div>
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded border-2 border-storm-yellow/50 bg-storm-yellow/10 flex items-center justify-center text-3xl glow-yellow flex-shrink-0">
            🎯
          </div>
          <div className="flex-1 min-w-0">
            {editing ? (
              <div className="flex gap-2 mb-1">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="bg-secondary border border-storm-yellow/50 rounded px-2 py-1 text-sm font-storm text-foreground flex-1 outline-none focus:border-storm-yellow"
                  maxLength={20}
                  autoFocus
                />
                <button
                  onClick={() => { setName(newName); setEditing(false); }}
                  className="px-3 py-1 bg-storm-yellow text-black text-xs font-storm rounded hover:brightness-110 transition-all"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="px-3 py-1 border border-border text-muted-foreground text-xs rounded hover:border-muted-foreground transition-all"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 mb-1">
                <h2 className="font-storm text-xl text-foreground tracking-wide">{name}</h2>
                <button onClick={() => setEditing(true)} className="text-muted-foreground hover:text-storm-yellow transition-colors">
                  <Icon name="Pencil" size={12} />
                </button>
              </div>
            )}
            <div className="text-xs text-muted-foreground font-mono-storm">@storm_hunter</div>
            <div className="flex gap-4 mt-2">
              <div>
                <div className="text-xs text-muted-foreground">Охот</div>
                <div className="font-storm text-storm-cyan">{ownedCars.length * 3}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Заработано</div>
                <div className="font-storm text-storm-yellow">12 500 МШ</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Машин</div>
                <div className="font-storm text-storm-green">{ownedCars.length}</div>
              </div>
            </div>
          </div>
        </div>
        <div className="mt-4 flex justify-center">
          <pre className="ascii-art text-center opacity-50 leading-relaxed">{ASCII_TORNADO}</pre>
        </div>
      </div>

      {/* Баланс + буст */}
      <div className="grid grid-cols-2 gap-3">
        <div className="card-storm rounded p-4 text-center">
          <div className="text-xs text-muted-foreground mb-1 font-mono-storm">БАЛАНС</div>
          <div className={`font-storm text-2xl text-storm-yellow transition-all ${boostEffect ? "animate-shake scale-110" : ""}`}>
            {balance.toLocaleString()}
          </div>
          <div className="text-xs text-muted-foreground">Магшиормов</div>
        </div>
        <button
          onClick={handleBoost}
          disabled={!canBoost}
          className={`card-storm rounded p-4 text-center transition-all duration-300 border
            ${canBoost
              ? "border-storm-green/50 hover:border-storm-green hover:bg-storm-green/10 glow-green cursor-pointer"
              : "border-border cursor-not-allowed opacity-60"
            }`}
        >
          <div className="text-xs text-muted-foreground mb-1 font-mono-storm">БУСТ</div>
          <div className="font-storm text-xl text-storm-green">+200 МШ</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {canBoost ? "✅ Доступен!" : formatTimer(boostTimer)}
          </div>
        </button>
      </div>

      {/* Гараж */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Icon name="Car" size={14} className="text-storm-cyan" />
          <span className="font-storm text-sm tracking-wider text-storm-cyan">ГАРАЖ</span>
          <span className="text-xs text-muted-foreground">({ownedCars.length} машин)</span>
        </div>

        {ownedCars.length === 0 ? (
          <div className="card-storm rounded p-8 text-center">
            <div className="text-4xl mb-2 opacity-30">🚗</div>
            <div className="text-muted-foreground text-sm">Гараж пуст. Купи первую машину в магазине!</div>
          </div>
        ) : (
          <div className="space-y-2">
            {ownedCars.map((oc, i) => {
              const car = CARS.find((c) => c.id === oc.id)!;
              return (
                <div
                  key={oc.id}
                  className="card-storm rounded p-3 flex items-center gap-3 animate-slide-in"
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  <div className="text-2xl">{car.emoji}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-storm text-sm">{car.name}</span>
                      <span className={`text-xs font-mono-storm font-bold ${levelColors[oc.level]}`}>
                        УР.{oc.level}
                      </span>
                      {oc.broken && (
                        <span className="text-xs text-storm-red font-mono-storm">⚠ СЛОМАНА</span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">{car.desc}</div>
                  </div>
                  <button
                    onClick={() => removeCar(oc.id)}
                    className="text-muted-foreground hover:text-storm-red transition-colors p-1 flex-shrink-0"
                    title="Убрать из гаража"
                  >
                    <Icon name="Trash2" size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────── МАГАЗИН ─────────── */
function ShopTab({
  balance, setBalance,
  ownedCars, setOwnedCars,
}: {
  balance: number; setBalance: (b: number) => void;
  ownedCars: OwnedCar[]; setOwnedCars: (c: OwnedCar[]) => void;
}) {
  const [page, setPage] = useState(0);
  const [notification, setNotification] = useState<string | null>(null);
  const CARS_PER_PAGE = 3;
  const totalPages = Math.ceil(CARS.length / CARS_PER_PAGE);
  const visibleCars = CARS.slice(page * CARS_PER_PAGE, (page + 1) * CARS_PER_PAGE);

  const notify = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 2500);
  };

  const getOwned = (carId: number) => ownedCars.find((c) => c.id === carId);

  const buyCar = (car: typeof CARS[0]) => {
    if (balance < car.price) { notify("❌ Недостаточно МШ!"); return; }
    if (getOwned(car.id)) { notify("⚠ Уже в гараже!"); return; }
    setBalance(balance - car.price);
    setOwnedCars([...ownedCars, { id: car.id, level: 1, broken: false }]);
    notify(`✅ ${car.name} куплен!`);
  };

  const upgradeCar = (oc: OwnedCar, car: typeof CARS[0]) => {
    if (oc.level >= 3) { notify("★ Максимальный уровень!"); return; }
    if (oc.broken) { notify("⚠ Сначала почини машину!"); return; }
    const cost = oc.level === 1 ? Math.floor(car.price * 0.5) : car.price;
    if (balance < cost) { notify(`❌ Нужно ${cost.toLocaleString()} МШ`); return; }
    setBalance(balance - cost);
    setOwnedCars(ownedCars.map((c) => c.id === oc.id ? { ...c, level: c.level + 1 } : c));
    notify(`⚡ ${car.name} → Ур.${oc.level + 1}!`);
  };

  const repairCar = (oc: OwnedCar, car: typeof CARS[0]) => {
    if (balance < 500) { notify("❌ Нужно 500 МШ для ремонта!"); return; }
    setBalance(balance - 500);
    setOwnedCars(ownedCars.map((c) => c.id === oc.id ? { ...c, broken: false } : c));
    notify(`🔧 ${car.name} отремонтирована!`);
  };

  const upgradeCost = (car: typeof CARS[0], level: number) =>
    level === 1 ? Math.floor(car.price * 0.5) : car.price;

  const levelBadge: Record<number, string> = { 1: "🟢 УР.1", 2: "🔵 УР.2", 3: "🟡 УР.3" };

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="card-storm rounded p-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xl">🔧</span>
          <span className="font-storm text-lg tracking-widest text-storm-cyan">МАГАЗИН ПЕРЕХВАТЧИКОВ</span>
        </div>
        <div className="text-xs text-muted-foreground font-mono-storm">
          10 машин · 3 уровня улучшений · Ремонт 500 МШ
        </div>
        <pre className="ascii-art-cyan text-center mt-2 opacity-30">{ASCII_CAR}</pre>
      </div>

      {notification && (
        <div className="text-center py-2 px-4 rounded border border-storm-yellow/50 bg-storm-yellow/10 text-storm-yellow text-sm font-storm animate-fade-up">
          {notification}
        </div>
      )}

      <div className="space-y-3">
        {visibleCars.map((car, i) => {
          const owned = getOwned(car.id);
          return (
            <div
              key={car.id}
              className={`card-storm rounded p-4 transition-all duration-200 animate-fade-up border
                ${owned ? "border-storm-cyan/30" : "border-transparent hover:border-border"}`}
              style={{ animationDelay: `${i * 0.08}s` }}
            >
              <div className="flex items-start gap-3">
                <div className={`text-3xl p-2 rounded ${owned ? "bg-storm-cyan/10" : "bg-secondary"}`}>
                  {car.emoji}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-storm text-base">{car.name}</span>
                    {owned && (
                      <span className="text-xs font-mono-storm">
                        {owned.broken ? "🔴 СЛОМАНА" : levelBadge[owned.level]}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">{car.desc}</div>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="font-storm text-storm-yellow text-sm">{car.price.toLocaleString()}</span>
                    <span className="text-xs text-muted-foreground">МШ</span>
                  </div>
                </div>
              </div>

              <div className="flex gap-2 mt-3 flex-wrap">
                {!owned ? (
                  <button
                    onClick={() => buyCar(car)}
                    disabled={balance < car.price}
                    className={`flex-1 py-2 px-3 rounded text-xs font-storm tracking-wider transition-all
                      ${balance >= car.price
                        ? "bg-storm-yellow text-black hover:brightness-110 glow-yellow"
                        : "bg-secondary text-muted-foreground cursor-not-allowed"
                      }`}
                  >
                    КУПИТЬ — {car.price.toLocaleString()} МШ
                  </button>
                ) : owned.broken ? (
                  <button
                    onClick={() => repairCar(owned, car)}
                    disabled={balance < 500}
                    className={`flex-1 py-2 px-3 rounded text-xs font-storm tracking-wider transition-all
                      ${balance >= 500
                        ? "bg-storm-orange text-black hover:brightness-110"
                        : "bg-secondary text-muted-foreground cursor-not-allowed"
                      }`}
                  >
                    🔧 РЕМОНТ — 500 МШ
                  </button>
                ) : owned.level < 3 ? (
                  <button
                    onClick={() => upgradeCar(owned, car)}
                    disabled={balance < upgradeCost(car, owned.level)}
                    className={`flex-1 py-2 px-3 rounded text-xs font-storm tracking-wider transition-all border
                      ${balance >= upgradeCost(car, owned.level)
                        ? "border-storm-cyan text-storm-cyan hover:bg-storm-cyan/10 glow-cyan"
                        : "border-border text-muted-foreground cursor-not-allowed"
                      }`}
                  >
                    ⚡ УР.{owned.level + 1} — {upgradeCost(car, owned.level).toLocaleString()} МШ
                  </button>
                ) : (
                  <div className="flex-1 py-2 px-3 rounded text-xs font-storm tracking-wider text-center text-storm-yellow border border-storm-yellow/30 bg-storm-yellow/5">
                    ★ МАКСИМАЛЬНЫЙ УРОВЕНЬ
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Пагинация */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
          className="flex items-center gap-1 px-4 py-2 rounded border border-border text-sm font-storm tracking-wider transition-all hover:border-muted-foreground disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Icon name="ChevronLeft" size={14} />
          НАЗАД
        </button>
        <div className="flex gap-1.5 items-center">
          {Array.from({ length: totalPages }).map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i)}
              className={`rounded-full transition-all duration-300 ${i === page ? "bg-storm-yellow w-4 h-2" : "bg-border w-2 h-2 hover:bg-muted-foreground"}`}
            />
          ))}
        </div>
        <button
          onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
          disabled={page === totalPages - 1}
          className="flex items-center gap-1 px-4 py-2 rounded border border-border text-sm font-storm tracking-wider transition-all hover:border-muted-foreground disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ВПЕРЁД
          <Icon name="ChevronRight" size={14} />
        </button>
      </div>
    </div>
  );
}

/* ─────────── ОХОТА НА ТОРНАДО ─────────── */
function StormTab({
  balance, setBalance,
  ownedCars, setOwnedCars,
}: {
  balance: number; setBalance: (b: number) => void;
  ownedCars: OwnedCar[]; setOwnedCars: (c: OwnedCar[]) => void;
}) {
  const [phase, setPhase] = useState<StormPhase>("select");
  const [selectedCar, setSelectedCar] = useState<OwnedCar | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [maxCountdown, setMaxCountdown] = useState(0);
  const [result, setResult] = useState<StormResult | null>(null);
  const [tornadoEf, setTornadoEf] = useState(1);

  const readyCars = ownedCars.filter((c) => !c.broken);

  const resolveHunt = useCallback((car: OwnedCar, ef: number, currentBalance: number) => {
    const efData = EF_DATA[ef];
    const levelBonus = (car.level - 1) * 10;
    const successChance = efData.chance + levelBonus;
    const roll = Math.random() * 100;
    const success = roll < successChance;
    const broken = !success && roll > 85;

    const successMessages = [
      "Чисто перехвачен! Данные записаны.",
      "Циклон взят под контроль! Великолепно!",
      "Мощный смерч задокументирован! Легенда!",
      "EF4 покорён! Твоё имя войдёт в историю!",
      "НЕВОЗМОЖНОЕ ВОЗМОЖНО! EF5 перехвачен!!!",
    ];
    const failMessages = [
      "Торнадо сменил курс. Промах.",
      "Слишком быстро. Не догнал.",
      "Опасно близко... но ушёл.",
      "EF4 не щадит слабаков. Отступление.",
      "EF5 разбросал всё на пути. Живой — уже победа.",
    ];
    const breakMessages = [
      "Небольшой ущерб от обломков. Ремонт нужен.",
      "Боковой удар! Машина повреждена.",
      "Смерч задел борт! Серьёзный ущерб.",
      "EF4 смял крышу! Экипаж цел, машина нет.",
      "EF5 разнёс перехватчик. Чудо что живы.",
    ];

    let reward = 0;
    let message = "";

    if (success) {
      reward = efData.reward + (car.level - 1) * Math.floor(efData.reward * 0.2);
      message = successMessages[ef - 1];
    } else if (broken) {
      message = breakMessages[ef - 1];
    } else {
      message = failMessages[ef - 1];
    }

    if (broken) {
      setOwnedCars(ownedCars.map((c) => c.id === car.id ? { ...c, broken: true } : c));
    }
    if (reward > 0) {
      setBalance(currentBalance + reward);
    }

    setResult({ ef, success, broken, reward, message });
    setPhase("result");
  }, [ownedCars, setOwnedCars, setBalance]);

  const startHunt = useCallback(() => {
    if (!selectedCar) return;
    const ef = Math.ceil(Math.random() * 5);
    const waitSec = Math.floor(Math.random() * 4 * 60 + 60);
    setTornadoEf(ef);
    setCountdown(waitSec);
    setMaxCountdown(waitSec);
    setPhase("waiting");

    let remaining = waitSec;
    const interval = setInterval(() => {
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
        resolveHunt(selectedCar, ef, balance);
      }
    }, 1000);
  }, [selectedCar, balance, resolveHunt]);

  const reset = () => {
    setPhase("select");
    setSelectedCar(null);
    setResult(null);
  };

  const formatCountdown = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const efData = EF_DATA[tornadoEf];

  /* Выбор машины */
  if (phase === "select") {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="card-storm rounded p-4 text-center">
          <div className="font-storm text-xl tracking-widest text-storm-yellow mb-1">🌪️ ОХОТА НА ТОРНАДО</div>
          <div className="text-xs text-muted-foreground font-mono-storm">Выбери перехватчик и отправляйся в рейд</div>
          <div className="mt-3 grid grid-cols-5 gap-2 text-xs">
            {[1, 2, 3, 4, 5].map((ef) => (
              <div key={ef} className="text-center">
                <div className={`font-storm font-bold ${EF_DATA[ef].efClass}`}>{EF_DATA[ef].name}</div>
                <div className="text-muted-foreground">{EF_DATA[ef].chance}%</div>
                <div className="text-storm-yellow font-mono-storm">{EF_DATA[ef].reward.toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>

        {readyCars.length === 0 ? (
          <div className="card-storm rounded p-8 text-center space-y-2">
            <div className="text-4xl">🚗</div>
            <div className="font-storm text-muted-foreground">Нет готовых машин</div>
            <div className="text-xs text-muted-foreground">Купи машину в магазине или почини сломанную</div>
          </div>
        ) : (
          <>
            <div className="text-xs text-muted-foreground font-mono-storm px-1">ВЫБЕРИ ПЕРЕХВАТЧИК:</div>
            <div className="space-y-2">
              {readyCars.map((oc) => {
                const car = CARS.find((c) => c.id === oc.id)!;
                const bonus = (oc.level - 1) * 10;
                const isSelected = selectedCar?.id === oc.id;
                return (
                  <button
                    key={oc.id}
                    onClick={() => setSelectedCar(oc)}
                    className={`w-full text-left card-storm rounded p-3 transition-all duration-200 border
                      ${isSelected
                        ? "border-storm-yellow glow-yellow bg-storm-yellow/5"
                        : "border-transparent hover:border-border"
                      }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">{car.emoji}</div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-storm text-sm">{car.name}</span>
                          <span className="text-xs text-storm-cyan font-mono-storm">УР.{oc.level}</span>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {bonus > 0 ? `+${bonus}% к базовому шансу` : "Базовый шанс успеха"}
                        </div>
                      </div>
                      {isSelected && <Icon name="CheckCircle" size={16} className="text-storm-yellow" />}
                    </div>
                  </button>
                );
              })}
            </div>

            <button
              onClick={startHunt}
              disabled={!selectedCar}
              className={`w-full py-4 rounded font-storm text-lg tracking-widest transition-all duration-300 border
                ${selectedCar
                  ? "bg-storm-red text-white border-storm-red hover:brightness-110 glow-red"
                  : "bg-secondary text-muted-foreground border-border cursor-not-allowed"
                }`}
            >
              🌪️ НАЧАТЬ ОХОТУ
            </button>
          </>
        )}
      </div>
    );
  }

  /* Ожидание */
  if (phase === "waiting") {
    const progress = maxCountdown > 0 ? ((maxCountdown - countdown) / maxCountdown) * 100 : 0;
    return (
      <div className="animate-fade-up space-y-4">
        <div className="card-storm rounded p-6 text-center space-y-4">
          <div className="font-storm text-storm-yellow tracking-widest animate-flicker">
            ⚡ ПЕРЕХВАТ В ПРОЦЕССЕ ⚡
          </div>

          <div className="relative w-36 h-36 mx-auto">
            <div className="absolute inset-0 rounded-full border border-storm-yellow/20 animate-pulse-ring" />
            <div className="absolute inset-0 rounded-full border border-storm-yellow/20 animate-pulse-ring" style={{ animationDelay: "0.7s" }} />
            <div className="absolute inset-3 rounded-full border border-storm-yellow/30 animate-spin-slow" />
            <div className="absolute inset-5 rounded-full border border-storm-cyan/30 animate-spin-reverse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-5xl animate-storm">🌪️</span>
            </div>
          </div>

          <div className="font-mono-storm text-5xl text-storm-yellow">
            {formatCountdown(countdown)}
          </div>

          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-storm-yellow transition-all duration-1000 rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className={`font-storm text-2xl ${efData.efClass}`}>
            ТОРНАДО {efData.name}
          </div>
          <div className="text-xs text-muted-foreground font-mono-storm">{efData.wind}</div>
          <div className="text-xs text-muted-foreground font-mono-storm">
            Шанс успеха: {efData.chance + (selectedCar ? (selectedCar.level - 1) * 10 : 0)}%
          </div>

          {selectedCar && (() => {
            const car = CARS.find((c) => c.id === selectedCar.id);
            return car ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground pt-2 border-t border-border">
                <span>{car.emoji}</span>
                <span className="font-storm">{car.name}</span>
                <span className="text-xs text-storm-cyan font-mono-storm">УР.{selectedCar.level}</span>
              </div>
            ) : null;
          })()}

          <div className="text-xs text-muted-foreground animate-flicker font-mono-storm">
            Сканирую атмосферу... ожидаю контакт...
          </div>
        </div>
      </div>
    );
  }

  /* Результат */
  if (phase === "result" && result) {
    const rd = EF_DATA[result.ef];
    return (
      <div className="animate-fade-up space-y-4">
        <div className={`card-storm rounded p-6 text-center space-y-3 border
          ${result.success ? "border-storm-green/40" : result.broken ? "border-storm-red/40" : "border-border"}`}>

          <pre className={`text-center font-mono-storm text-xs ${result.success ? "text-storm-green" : "text-storm-red"}`}>
            {result.success ? ASCII_SUCCESS : ASCII_FAIL}
          </pre>

          <div className={`font-storm text-3xl tracking-widest
            ${result.success ? "text-storm-green" : result.broken ? "text-storm-red" : "text-muted-foreground"}`}>
            {result.success ? "УСПЕХ!" : result.broken ? "МАШИНА РАЗБИТА" : "ПРОВАЛ"}
          </div>

          <div className={`inline-block px-3 py-1 rounded font-storm text-sm ${rd.efClass} border border-current/30`}>
            ТОРНАДО {rd.name} · {rd.wind}
          </div>

          <div className="text-sm text-muted-foreground font-mono-storm leading-relaxed max-w-xs mx-auto">
            {result.message}
          </div>

          {result.reward > 0 && (
            <div className="flex items-center justify-center gap-2 py-3 border-t border-border">
              <Icon name="Coins" size={20} className="text-storm-yellow" />
              <span className="font-storm text-2xl text-storm-yellow">+{result.reward.toLocaleString()} МШ</span>
            </div>
          )}

          {result.broken && (
            <div className="text-xs text-storm-red font-mono-storm border border-storm-red/30 rounded p-2 bg-storm-red/5">
              ⚠ Машина повреждена — требуется ремонт 500 МШ в магазине
            </div>
          )}
        </div>

        {/* Шкала шансов */}
        <div className="card-storm rounded p-3 space-y-2">
          <div className="text-xs text-muted-foreground font-mono-storm mb-2">ШАНСЫ И НАГРАДЫ</div>
          {[1, 2, 3, 4, 5].map((ef) => {
            const d = EF_DATA[ef];
            const bonus = selectedCar ? (selectedCar.level - 1) * 10 : 0;
            const chance = Math.min(100, d.chance + bonus);
            return (
              <div key={ef} className="flex items-center gap-2 text-xs">
                <span className={`font-storm w-8 ${d.efClass}`}>{d.name}</span>
                <div className="flex-1 h-1 bg-secondary rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${d.efClass}`} style={{ width: `${chance}%`, backgroundColor: "currentColor", opacity: 0.7 }} />
                </div>
                <span className="text-muted-foreground w-8 text-right font-mono-storm">{chance}%</span>
                <span className="text-storm-yellow w-16 text-right font-mono-storm">{d.reward.toLocaleString()}</span>
              </div>
            );
          })}
        </div>

        <button
          onClick={reset}
          className="w-full py-3 rounded font-storm tracking-widest text-sm border border-storm-yellow text-storm-yellow hover:bg-storm-yellow/10 transition-all"
        >
          🌪️ НОВАЯ ОХОТА
        </button>
      </div>
    );
  }

  return null;
}

const LS_BOOST_KEY = "storm_boost_used_at";

function loadBoostTime(): number {
  try {
    const v = localStorage.getItem(LS_BOOST_KEY);
    return v ? parseInt(v, 10) : 0;
  } catch (e) {
    console.warn("localStorage unavailable", e);
    return 0;
  }
}

function saveBoostTime(ts: number) {
  try {
    localStorage.setItem(LS_BOOST_KEY, String(ts));
  } catch (e) {
    console.warn("localStorage unavailable", e);
  }
}

/* ─────────── ГЛАВНЫЙ КОМПОНЕНТ ─────────── */
export default function Index() {
  const [tab, setTab] = useState<Tab>("profile");
  const [balance, setBalance] = useState(5000);
  const [name, setName] = useState("Охотник");
  const [ownedCars, setOwnedCars] = useState<OwnedCar[]>([]);
  const [lastBoost, setLastBoost] = useState<number>(() => loadBoostTime());

  return (
    <div className="min-h-screen bg-background noise bg-grid">
      <TopBar tab={tab} setTab={setTab} balance={balance} />
      <main className="max-w-2xl mx-auto px-4 py-5 pb-10">
        {tab === "profile" && (
          <ProfileTab
            balance={balance} setBalance={setBalance}
            name={name} setName={setName}
            ownedCars={ownedCars} setOwnedCars={setOwnedCars}
            lastBoost={lastBoost} setLastBoost={setLastBoost}
          />
        )}
        {tab === "shop" && (
          <ShopTab
            balance={balance} setBalance={setBalance}
            ownedCars={ownedCars} setOwnedCars={setOwnedCars}
          />
        )}
        {tab === "storm" && (
          <StormTab
            balance={balance} setBalance={setBalance}
            ownedCars={ownedCars} setOwnedCars={setOwnedCars}
          />
        )}
      </main>
    </div>
  );
}