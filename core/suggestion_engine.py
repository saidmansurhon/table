"""Pure-Python conflict search used by the Django teacher scheduling form.

This engine does not generate or change an entire timetable. It ranks
single-class alternatives, one-blocker relocations and two-class swaps.
The Django layer owns permissions, ORM access, signing, and persistence.
"""

from dataclasses import replace
from dataclasses import dataclass

DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')


@dataclass(frozen=True)
class Position:
    day: int
    start: int
    end: int
    room: int


@dataclass(frozen=True)
class Lesson:
    key: str
    batch_ids: frozenset
    faculty: int
    subject: int
    position: Position
    strength: int
    fixed_room: int | None = None
    shift: tuple | None = None  # (start, end, lunch_start, lunch_end)
    movable: bool = False


@dataclass(frozen=True)
class RoomInfo:
    pk: int
    name: str
    capacity: int
    available: bool = True


@dataclass(frozen=True)
class Proposal:
    kind: str
    label: str
    target: Position
    blocker_key: str | None = None
    blocker_new: Position | None = None
    score: int = 0


def reasons(a, b):
    if a.position.day != b.position.day:
        return ()
    if a.position.start >= b.position.end or b.position.start >= a.position.end:
        return ()
    result = []
    if a.position.room == b.position.room:
        result.append('room')
    if a.faculty == b.faculty:
        result.append('faculty')
    if a.batch_ids & b.batch_ids:
        result.append('batch')
    return tuple(result)


def collisions(target, existing, exclude=()):
    ignored = set(exclude)
    return [(other, reasons(target, other)) for other in existing
            if other.key not in ignored and reasons(target, other)]


def position_allowed(lesson, pos, room_map):
    room = room_map.get(pos.room)
    if not room or not room.available or room.capacity < lesson.strength:
        return False
    if lesson.fixed_room and lesson.fixed_room != pos.room:
        return False
    if pos.day not in range(6) or pos.start < 10 or pos.end > 18:
        return False
    if pos.start >= pos.end or pos.end - pos.start != lesson.position.end - lesson.position.start:
        return False
    if lesson.shift:
        shift_start, shift_end, lunch_start, lunch_end = lesson.shift
        if pos.start < shift_start or pos.end > shift_end:
            return False
        if pos.start < lunch_end and pos.end > lunch_start:
            return False
    return True


def valid(lesson, existing, rooms, exclude=()):
    room_map = {room.pk: room for room in rooms}
    return (position_allowed(lesson, lesson.position, room_map)
            and not collisions(lesson, existing, exclude=exclude))


def alternatives(lesson, rooms, reference=None):
    """Deterministic preference order: room, time, then other days."""
    reference = reference or lesson.position
    duration = lesson.position.end - lesson.position.start
    starts = list(range(10, 19 - duration))
    starts.sort(key=lambda start: (start != reference.start, abs(start - reference.start)))
    room_ids = [r.pk for r in rooms]
    room_ids.sort(key=lambda room: (room != reference.room, room))
    days = list(range(6))
    days.sort(key=lambda day: (day != reference.day, abs(day - reference.day)))
    positions = [Position(d, s, s + duration, r) for d in days for s in starts for r in room_ids]
    positions.sort(key=lambda p: (p.day != reference.day, p.start != reference.start,
                                  p.room != reference.room, abs(p.start - reference.start),
                                  abs(p.day - reference.day), p.room))
    return positions


def _score(base, new, extra=0):
    return ((0 if base.day == new.day else 20)
            + (0 if base.start == new.start else 8 + abs(base.start - new.start))
            + (0 if base.room == new.room else 2) + extra)


def suggest(target, existing, rooms, *, original=None, max_results=24):
    """Search suggestions without mutating input or stored lessons.

    For complicated proposals only one blocking existing lesson may be moved;
    combined classes and lessons the user cannot edit must be marked movable=False.
    """
    available = {room.pk: room for room in rooms}
    exclude = (original.key,) if original else ()
    problem = collisions(target, existing, exclude=exclude)
    proposals = []
    seen = set()

    def add(p):
        key = (p.kind, p.target, p.blocker_key, p.blocker_new)
        if key not in seen:
            proposals.append(p)
            seen.add(key)

    # 1. Direct alternatives: room-only, time on same day, other day.
    for pos in alternatives(target, rooms):
        if pos == target.position:
            continue
        candidate = replace(target, position=pos)
        if valid(candidate, existing, rooms, exclude=exclude):
            if pos.day == target.position.day and pos.start == target.position.start:
                kind, label = 'room', f'Free room: {available[pos.room].name}; same day and time'
            elif pos.day == target.position.day:
                kind, label = 'time', f'New time: {pos.start}:00–{pos.end}:00, {available[pos.room].name}'
            else:
                kind, label = 'day', f'Another day: {DAY_NAMES[pos.day]}, {pos.start}:00–{pos.end}:00, {available[pos.room].name}'
            add(Proposal(kind, label, pos, score=_score(target.position, pos)))

    # 2. Keep exact requested time/room, move ONE blocking lesson.
    if len(problem) == 1:
        blocker, why = problem[0]
        if blocker.movable and blocker.key.startswith('entry:'):
            room_map = {r.pk: r for r in rooms}
            if position_allowed(target, target.position, room_map):
                excludes = (*exclude, blocker.key)
                if not collisions(target, existing, exclude=excludes):
                    for b_pos in alternatives(blocker, rooms):
                        if b_pos == blocker.position:
                            continue
                        relocated = replace(blocker, position=b_pos)
                        if (valid(relocated, existing, rooms, exclude=excludes)
                                and not reasons(target, relocated)):
                            add(Proposal('move_blocker',
                                         f'Move blocking class {blocker.key} to {DAY_NAMES[b_pos.day]}, '
                                         f'{b_pos.start}:00–{b_pos.end}:00, {room_map[b_pos.room].name}; '
                                         f'keep your requested slot ({", ".join(why)} conflict)',
                                         target.position, blocker.key, b_pos,
                                         score=_score(blocker.position, b_pos, extra=45)))

                    # 3. Swap: when editing existing target, blocker moves to its old slot.
                    if original and original.position != target.position:
                        relocated = replace(blocker, position=original.position)
                        if (position_allowed(relocated, original.position, room_map)
                                and valid(relocated, existing, rooms, exclude=excludes)
                                and not reasons(target, relocated)):
                            add(Proposal('swap',
                                         f'Swap with class {blocker.key}: it takes your old slot',
                                         target.position, blocker.key, original.position,
                                         score=48))

    # Group by action; show variety rather than 24 nearly identical room changes.
    budgets = {'room': 7, 'time': 7, 'day': 6, 'move_blocker': 3, 'swap': 1}
    proposals.sort(key=lambda p: (p.score, p.kind, p.label))
    output = []
    for proposal in proposals:
        if budgets.get(proposal.kind, 0) > 0:
            output.append(proposal)
            budgets[proposal.kind] -= 1
        if len(output) >= max_results:
            break
    return output
