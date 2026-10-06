"""Character-independent planar IK and in-place walking phase coefficients."""
import math


def solve_two_bone(root, target, upper_length, lower_length, bend_sign=1):
    values = (*root, *target, upper_length, lower_length, bend_sign)
    if not all(math.isfinite(v) for v in values) or min(upper_length, lower_length) <= 0:
        raise ValueError('Finite coordinates and positive bone lengths are required')
    if bend_sign not in (-1, 1):
        raise ValueError('bend_sign must be -1 or 1')
    dx, dy = target[0]-root[0], target[1]-root[1]
    distance = math.hypot(dx, dy)
    ux, uy = (dx/distance, dy/distance) if distance > 1e-12 else (0., 1.)
    reach = min(upper_length+lower_length, max(abs(upper_length-lower_length), distance))
    if reach < 1e-12:
        knee = (root[0]+bend_sign*upper_length, root[1])
        ankle = tuple(root)
    else:
        along = (upper_length**2-lower_length**2+reach**2)/(2*reach)
        height = math.sqrt(max(0., upper_length**2-along**2))
        knee = (root[0]+ux*along-uy*height*bend_sign,
                root[1]+uy*along+ux*height*bend_sign)
        ankle = (root[0]+ux*reach, root[1]+uy*reach)
    return {'root':tuple(root), 'knee':knee, 'ankle':ankle,
            'upper_length':math.dist(root,knee), 'lower_length':math.dist(knee,ankle),
            'reach_error':math.dist(ankle,target),
            'upper_angle':math.atan2(knee[0]-root[0],knee[1]-root[1]),
            'lower_angle':math.atan2(ankle[0]-knee[0],ankle[1]-knee[1])}


def walk_phase(phase):
    if not math.isfinite(phase):
        raise ValueError('phase must be finite')
    def foot(p):
        p %= 1
        if p < .5:
            return {'forward':1-4*p,'lift':0.,'stance':True}
        t = (p-.5)*2
        # Ease swing; continuous position and a zero-velocity lift at its ends.
        return {'forward':-math.cos(math.pi*t),'lift':math.sin(math.pi*t)**2,'stance':False}
    return {'left':foot(phase), 'right':foot(phase+.5),
            'pelvis_bob':-math.cos(4*math.pi*phase)}
