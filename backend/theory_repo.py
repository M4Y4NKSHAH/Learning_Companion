FLASHCARD_REPOSITORY = {
    "Physics": {
        "Class 10": {
            "cards": [
                {
                    "id": "p10_c1",
                    "topic": "Newton's Second Law",
                    "question": "What is the core formula for Newton's Second Law and how does force interact with mass?",
                    "answer": "• Core Equation: Force = Mass x Acceleration (F = m x a).\n• Core Metric: Applying an unbalanced external force to an object causes it to change its velocity over time.\n• Computational Breakdown: A 10 kg object accelerating at 5 m/s² experiences a net force of exactly 50 Newtons (10 kg x 5 m/s² = 50 N)."
                },
                {
                    "id": "p10_c2",
                    "topic": "Friction Dynamics",
                    "question": "What is friction and how does its vector orientation behave relative to motion?",
                    "answer": "• Definition: Friction is a specific contact force that opposes movement between surfaces.\n• Vector Boundary: It always acts in a path exactly opposite to the direction of intended or active motion, creating systemic resistance."
                },
                {
                    "id": "p10_c3",
                    "topic": "Kinematics & Constant Velocity",
                    "question": "What is the mathematical value of acceleration when a vehicle travels at a constant velocity?",
                    "answer": "• Constant Velocity Rule: Constant velocity means speed and direction remain perfectly steady over time.\n• Acceleration Profile: Because velocity variation is exactly zero, acceleration is mathematically 0 m/s² (e.g., a car traveling steadily at 20 m/s for 10 seconds has 0 acceleration)."
                }
            ],
            "quizzes": [
                {
                    "id": "p10_q1",
                    "text": "A 10kg structural mass experiences a constant acceleration of 5 m/s². Calculate the active net force vector acting on it in Newtons.",
                    "concept": "Newton's Second Law",
                    "expected_answer": "50",
                    "hint": "Recall Newton's Second Law relating force, mass, and acceleration: Force = Mass * Acceleration (F = m * a). Multiply the given mass by the acceleration.",
                    "solution": "1. Formula: Net Force F = m * a (Mass * Acceleration)\n2. Given: Mass m = 10 kg, Acceleration a = 5 m/s²\n3. Calculation: F = 10 kg * 5 m/s² = 50 N\n\nDirect Answer: 50 Newtons (N)."
                },
                {
                    "id": "p10_q2",
                    "text": "If an automated transport vehicle moves at a perfectly uniform constant velocity of 20 m/s for 10 seconds, what is its rate of acceleration in m/s²?",
                    "concept": "Kinematics",
                    "expected_answer": "0",
                    "hint": "Remember the fundamental definition of acceleration: it represents the rate of change of velocity over time. If the velocity is constant and unchanging, does any acceleration occur?",
                    "solution": "1. Formula: Acceleration a = (v_final - v_initial) / t = Δv / Δt\n2. Given: Velocity is strictly constant at 20 m/s, so Δv = 0 m/s\n3. Calculation: a = 0 m/s / 10 s = 0 m/s²\n\nDirect Answer: 0 m/s²."
                }
            ],
            "finalExam": [
                { 
                  "qId": "p10_f1", 
                  "moduleOrigin": "Module 1: Newton's Second Law",
                  "text": "A mechanical component with an exact mass of 8 kg accelerates uniformly across a smooth linear track at 4 m/s². Compute the total active horizontal force applied in Newtons (Provide numerical integer only).", 
                  "expected": "32",
                  "formula": "Force = Mass x Acceleration (F = m x a)",
                  "misconception": "Student might be dividing the variables (8/4 or 4/8) instead of applying multiplication metrics."
                },
                { 
                  "qId": "p10_f2", 
                  "moduleOrigin": "Module 2: Friction Dynamics",
                  "text": "An automated storage block is dragged along a straight conveyor belt line toward the north direction. In what vector heading direction does the surface friction force operate?", 
                  "expected": "south",
                  "formula": "Friction Vector = -1 x (Active Vector Path Heading Direction)",
                  "misconception": "Student might think friction assists movement or acts downward alongside gravity parameters."
                },
                { 
                  "qId": "p10_f3", 
                  "moduleOrigin": "Module 3: Kinematics & Constant Velocity",
                  "text": "A high-speed tracking train operates along a straight route at a perfectly constant velocity of 45 m/s for a duration of 60 seconds. What is the active acceleration rate in m/s²?", 
                  "expected": "0",
                  "formula": "Acceleration (a) = Delta Velocity / Delta Time (Δv / Δt)",
                  "misconception": "Student might try to calculate a change by multiplying 45 x 60, forgetting that constant velocity means acceleration is absolute zero."
                }
            ]
        },
        "Class 11-12": {
            "cards": [
                {
                    "id": "p12_c1",
                    "topic": "Projectile Vector Splitting",
                    "question": "How is a projectile's motion vector decoupled in a two-dimensional ballistic plane?",
                    "answer": "• Decoupled Components: Motion is split into entirely independent horizontal (x) and vertical (y) vector streams under gravity (g = 9.8 m/s²).\n• Horizontal Trajectory: Air resistance is ignored, so horizontal acceleration is zero (ax = 0) and horizontal velocity stays completely constant."
                },
                {
                    "id": "p12_c2",
                    "topic": "Peak Flight Constraints",
                    "question": "What specific boundary condition occurs to a projectile's velocity components at its maximum height?",
                    "answer": "• Vertical Peak Value: At absolute maximum height of its flight path, vertical velocity drops precisely to zero (vy = 0).\n• Horizontal State: The horizontal velocity vector remains active, stable, and unchanged."
                },
                {
                    "id": "p12_c3",
                    "topic": "Rotational Torque Rules",
                    "question": "What acts as the rotational analogue to linear force and how is rotational inertia measured?",
                    "answer": "• Torque Analogue: Torque is the rotational equivalent of a linear force, measuring a force's capacity to induce angular acceleration around a pivot.\n• Moment of Inertia: Rotational resistance is quantified by Moment of Inertia (I), which depends on mass distribution relative to the axis."
                }
            ],
            "quizzes": [
                {
                    "id": "p12_q1",
                    "text": "A research payload is launched ballistically into a parabolic path. When it reaches its absolute maximum peak height, what is the value of its vertical velocity component in m/s?",
                    "concept": "Projectile Motion",
                    "expected_answer": "0",
                    "hint": "Consider the vertical motion under gravity: as the projectile rises, gravity decelerates it until it momentarily stops rising at the very apex before descending. What must the vertical velocity be at that exact turning point?",
                    "solution": "1. Principle: At the vertex of a parabolic trajectory, the vertical velocity vector v_y momentarily drops to zero before reversing direction.\n2. Note: The horizontal velocity v_x remains active and unchanged throughout flight.\n\nDirect Answer: 0 m/s."
                }
            ],
            "finalExam": [
                { 
                  "qId": "p12_f1", 
                  "moduleOrigin": "Module 1: Projectile Component Systems",
                  "text": "During an idealized ballistic flight tracking projectile dynamics, calculate the value of the vertical velocity component vector in m/s at the absolute peak height coordinates.", 
                  "expected": "0",
                  "formula": "Vertical Velocity at Peak Vertex (v_y) = 0",
                  "misconception": "Student might mistake total velocity for zero, or try to factor in the active horizontal speed value."
                }
            ]
        },
        "Undergraduate": {
            "cards": [
                {
                    "id": "pug_c1",
                    "topic": "The Lagrangian Function",
                    "question": "What is the structural definition of the Lagrangian function (L) in analytical mechanics?",
                    "answer": "• Energy Definition: The Lagrangian replaces vector tracking with scalar tracking models within constraints.\n• Fundamental Relation: It is calculated as Kinetic Energy (T) minus Potential Energy (V), resulting in the formula: L = T - V.\n• Equations of Motion: Plugged into Euler-Lagrange equations to resolve system tracking paths cleanly."
                },
                {
                    "id": "pug_c2",
                    "topic": "Hamiltonian Phase Spaces",
                    "question": "How does the Hamiltonian formulation shift mechanical tracking variables?",
                    "answer": "• Variable Shift: Transitions from generalized velocities to conjugate momenta parameters.\n• Total System Energy: Represents total mechanical energy (H = T + V), generating first-order partial differential equations across continuous phase space fields."
                },
                {
                    "id": "pug_c3",
                    "topic": "Quantum State Operators & Observables",
                    "question": "How do quantum mechanical operators correspond to physical measurable observables?",
                    "answer": "• Hermitian Operators: Physical observables (energy, momentum) correspond to linear Hermitian operators in Hilbert space.\n• Eigenvalue Principle: Measurement outcomes yield real eigenvalues corresponding to operator eigenstates."
                }
            ],
            "quizzes": [
                {
                    "id": "pug_q1",
                    "text": "What fundamental scalar energy formula connects Kinetic Energy (T) and Potential Energy (V) to define the system Lagrangian (L)?",
                    "concept": "Lagrangian Mechanics",
                    "expected_answer": "L = T - V",
                    "hint": "In analytical mechanics, the Lagrangian is defined as the difference between the system's kinetic energy and its potential energy (unlike the Hamiltonian which sums them).",
                    "solution": "1. Principle: The Lagrangian function L represents scalar energy within generalized coordinates.\n2. Formula: Lagrangian (L) = Kinetic Energy (T) - Potential Energy (V)\n\nDirect Answer: L = T - V."
                }
            ],
            "finalExam": [
                { 
                  "qId": "pug_f1", 
                  "moduleOrigin": "Module 1: Analytical Mechanics",
                  "text": "Input the baseline scalar equation defining the system state Lagrangian (L) as a function of kinetic energy (T) and potential energy (V) using standard notation.", 
                  "expected": "l=t-v",
                  "formula": "Lagrangian Function (L) = Kinetic Energy (T) - Potential Energy (V)",
                  "misconception": "Student might inadvertently add the metrics (T+V), which instead characterizes the system Hamiltonian function."
                }
            ]
        }
    },
    "Biology": {
        "Class 10": {
            "cards": [
                {
                    "id": "b10_c1",
                    "topic": "Cellular Energy & Mitochondria",
                    "question": "What is the primary function of mitochondria in a eukaryotic cell?",
                    "answer": "• Cellular Organelles: Mitochondria are specialized double-membrane organelles inside cells.\n• Power Generation: They produce ATP through cellular respiration, converting glucose and oxygen into usable chemical energy."
                },
                {
                    "id": "b10_c2",
                    "topic": "Photosynthesis & Light Reactions",
                    "question": "How do plants convert sunlight into chemical energy during photosynthesis?",
                    "answer": "• Chloroplast Function: Chlorophyll pigments capture solar photons inside thylakoid membranes.\n• Chemical Output: Light-dependent reactions convert water and carbon dioxide into glucose and oxygen gas (6CO2 + 6H2O -> C6H12O6 + 6O2)."
                },
                {
                    "id": "b10_c3",
                    "topic": "DNA Structure & Double Helix",
                    "question": "What structural components make up the genetic code in a DNA double helix?",
                    "answer": "• Sugar-Phosphate Backbone: Alternating deoxyribose sugars and phosphate molecules form structural sides.\n• Nitrogenous Base Pairs: Adenine pairs with Thymine (A-T), and Cytosine pairs with Guanine (C-G) to store sequence data."
                }
            ],
            "quizzes": [
                {
                    "id": "b10_q1",
                    "text": "Which membrane-bound organelle acts as the main power plant of eukaryotic cells by generating ATP?",
                    "concept": "Cellular Energy",
                    "expected_answer": "Mitochondria",
                    "hint": "Think of the double-membraned organelle often called the 'powerhouse of the cell' where cellular respiration and ATP synthesis take place.",
                    "solution": "1. Principle: Cellular respiration occurs in the mitochondria, where glucose and oxygen are converted into ATP (adenosine triphosphate).\n2. Function: Mitochondria serve as the primary chemical power generator for eukaryotic cells.\n\nDirect Answer: Mitochondria (or Mitochondrion)."
                }
            ],
            "finalExam": [
                { 
                  "qId": "b10_f1", 
                  "moduleOrigin": "Module 1: Cellular Power Plants",
                  "text": "What is the primary chemical compound that mitochondria produce to store and transfer energy within eukaryotic cells? (Provide the 3-letter abbreviation only)", 
                  "expected": "ATP",
                  "formula": "Adenosine Triphosphate Synthesis",
                  "misconception": "Student might think of glucose or ADP instead of the immediate energy currency."
                }
            ]
        },
        "Class 11-12": {
            "cards": [
                {
                    "id": "b12_c1",
                    "topic": "Transcription Enzymes",
                    "question": "What specific enzyme binds to DNA to synthesize single-stranded mRNA during transcription?",
                    "answer": "• Transcription Boundary: Transcription converts genetic data from DNA into a complementary RNA sequence.\n• Active Enzyme: RNA Polymerase binds to a promoter region, unzips the helix, and matches nucleotides to build the single-stranded mRNA."
                },
                {
                    "id": "b12_c2",
                    "topic": "Enzyme Kinetics & Catalysis",
                    "question": "How do enzyme biological catalysts increase the rate of metabolic reactions?",
                    "answer": "• Activation Energy Barrier: Enzymes lower the activation energy required to initiate chemical reactions.\n• Active Site Specificity: Substrates bind precisely into enzyme active sites forming unstable transition-state complexes."
                },
                {
                    "id": "b12_c3",
                    "topic": "Cellular Respiration & Krebs Cycle",
                    "question": "What takes place during the citric acid (Krebs) cycle within the mitochondrial matrix?",
                    "answer": "• Pyruvate Processing: Acetyl-CoA is oxidized through a series of enzyme-driven steps.\n• Electron Carriers: Produces NADH, FADH2, and ATP while releasing CO2 as a byproduct to drive electron transport chains."
                }
            ],
            "quizzes": [
                {
                    "id": "b12_q1",
                    "text": "Name the enzyme that unzips the DNA double helix and binds to the promoter region to synthesize mRNA.",
                    "concept": "Transcription Enzymes",
                    "expected_answer": "RNA Polymerase",
                    "hint": "This enzyme synthesizes RNA by reading the template DNA strand during transcription. Its name reflects the polymer it constructs.",
                    "solution": "1. Principle: During transcription, RNA Polymerase recognizes and binds to the promoter sequence, unzips the DNA strands, and catalyzes the synthesis of complementary single-stranded mRNA.\n\nDirect Answer: RNA Polymerase."
                }
            ],
            "finalExam": [
                { 
                  "qId": "b12_f1", 
                  "moduleOrigin": "Module 1: Transcription Dynamics",
                  "text": "Identify the primary enzyme responsible for synthesizing single-stranded RNA from a DNA template during transcription. (Provide the standard multi-word name)", 
                  "expected": "RNA Polymerase",
                  "formula": "DNA transcription to mRNA pathway",
                  "misconception": "Student might mistake it for DNA Polymerase or Helicase."
                }
            ]
        },
        "Undergraduate": {
            "cards": [
                {
                    "id": "bug_c1",
                    "topic": "Epigenetic Modification",
                    "question": "What group of specialized enzymes catalyzes the addition of methyl groups to histone tails to enforce silencing?",
                    "answer": "• Chromatin Alterations: Epigenetics adjusts gene expression without changing the core underlying DNA sequence.\n• Silencing Mechanism: Histone Methyltransferases add methyl groups to histone tails, compressing chromatin to silence transcription."
                },
                {
                    "id": "bug_c2",
                    "topic": "Signal Transduction Cascades",
                    "question": "How do cell-surface G-protein coupled receptors (GPCRs) amplify extracellular signals inside cells?",
                    "answer": "• Receptor Activation: Ligand binding induces conformational change in seven-transmembrane GPCR domain.\n• Second Messengers: Activates heterotrimeric G-proteins to trigger cAMP or IP3 secondary messenger cascades."
                },
                {
                    "id": "bug_c3",
                    "topic": "CRISPR-Cas9 Gene Editing",
                    "question": "What mechanism enables the CRISPR-Cas9 complex to introduce site-specific double-stranded breaks in DNA?",
                    "answer": "• Guide RNA Targeting: Synthetic single guide RNA (sgRNA) matches a 20-nucleotide target genomic sequence.\n• Endonuclease Cleavage: Cas9 enzyme scans for adjacent PAM motifs and cuts target DNA strands precisely."
                }
            ],
            "quizzes": [
                {
                    "id": "bug_q1",
                    "text": "Which class of enzymes catalyzes the transfer of methyl groups to histone proteins, causing chromatin condensation?",
                    "concept": "Epigenetic Modification",
                    "expected_answer": "Histone Methyltransferases",
                    "hint": "Combine the target substrate (histone), the modifying functional group (methyl), and the standard suffix for enzymes that transfer groups.",
                    "solution": "1. Principle: Histone Methyltransferases (HMTs) catalyze the transfer of methyl groups from SAM to lysine or arginine residues of histone proteins, altering chromatin structure and silencing transcription.\n\nDirect Answer: Histone Methyltransferases (HMTs)."
                }
            ],
            "finalExam": [
                { 
                  "qId": "bug_f1", 
                  "moduleOrigin": "Module 1: Chromatin Remodeling",
                  "text": "What class of enzymes is responsible for adding methyl groups to histone proteins to compact chromatin and silence gene expression? (Provide the plural name, e.g., histone methyltransferases)", 
                  "expected": "histone methyltransferases",
                  "formula": "Histone Modification Cascade",
                  "misconception": "Student might mistake it for DNA methyltransferases or histone acetyltransferases."
                }
            ]
        }
    },
    "Mathematics": {
        "Class 10": {
            "cards": [
                {
                    "id": "m10_c1",
                    "topic": "Linear Equations",
                    "question": "How do you solve for x in a linear equation like 3x + 7 = 22?",
                    "answer": "• Balance Rule: A linear equation must remain balanced by applying equal transformations to both sides.\n• Isolation Sequence: Subtract 7 from both sides to clear addition (3x = 15), then apply inverse multiplication by dividing by 3 to find x = 5."
                },
                {
                    "id": "m10_c2",
                    "topic": "Quadratic Formula & Discriminant",
                    "question": "What is the Quadratic Formula and how does the discriminant indicate root types?",
                    "answer": "• Solution Formula: x = (-b ± √(b² - 4ac)) / (2a) solves any quadratic equation ax² + bx + c = 0.\n• Discriminant Metric: Δ = b² - 4ac determines roots: Δ > 0 (two real roots), Δ = 0 (one real root), Δ < 0 (complex roots)."
                },
                {
                    "id": "m10_c3",
                    "topic": "Pythagorean Theorem & Trigonometry",
                    "question": "How do side ratios define Sine, Cosine, and Tangent in right-angled triangles?",
                    "answer": "• Fundamental Theorem: a² + b² = c² relates leg lengths to hypotenuse in right triangles.\n• Trigonometric Ratios: sin(θ) = Opposite/Hypotenuse, cos(θ) = Adjacent/Hypotenuse, tan(θ) = Opposite/Adjacent."
                }
            ],
            "quizzes": [
                {
                    "id": "m10_q1",
                    "text": "In the linear algebraic equation 2x - 5 = 11, what is the value of x?",
                    "concept": "Linear Equations",
                    "expected_answer": "8",
                    "hint": "Isolate the variable term: first add 5 to both sides of the equation, then divide both sides by the coefficient 2.",
                    "solution": "1. Given Equation: 2x - 5 = 11\n2. Step 1: Add 5 to both sides: 2x = 11 + 5 = 16\n3. Step 2: Divide both sides by 2: x = 16 / 2 = 8\n\nDirect Answer: x = 8."
                }
            ],
            "finalExam": [
                { 
                  "qId": "m10_f1", 
                  "moduleOrigin": "Module 1: Linear Algebraic Transformations",
                  "text": "Solve for the variable x in the linear algebraic equation: 5x + 12 = 47. (Provide numerical integer only)", 
                  "expected": "7",
                  "formula": "x = (C - B) / A for Ax + B = C",
                  "misconception": "Student might add 12 to 47 instead of subtracting, or divide incorrectly."
                }
            ]
        },
        "Class 11-12": {
            "cards": [
                {
                    "id": "m12_c1",
                    "topic": "The Power Rule",
                    "question": "What is the derivative of the polynomial function f(x) = 3x² + 2x using the Power Rule?",
                    "answer": "• Derivative Definition: Calculates the instantaneous rate of change or slope of a function at an exact coordinate point.\n• Calculation: Applying the Power Rule (the derivative of x^n is n * x^(n-1)) to each term independently yields exactly 6x + 2."
                },
                {
                    "id": "m12_c2",
                    "topic": "Integration & Definite Integrals",
                    "question": "How does integration reverse differentiation to find the area under a curve?",
                    "answer": "• Antiderivative Concept: Integration calculates accumulation by reversing derivative operations (∫ x^n dx = x^(n+1)/(n+1) + C).\n• Definite Integral: Evaluates the total area bounded by a function between limits a and b: ∫[a to b] f(x)dx = F(b) - F(a)."
                },
                {
                    "id": "m12_c3",
                    "topic": "Limits & Continuity",
                    "question": "What condition must be satisfied for a mathematical function f(x) to be continuous at x = c?",
                    "answer": "• Existence Criteria: The function value f(c) must be defined and the limit lim(x->c) f(x) must exist.\n• Continuity Match: The left-hand limit, right-hand limit, and actual function value must be equal: lim(x->c) f(x) = f(c)."
                }
            ],
            "quizzes": [
                {
                    "id": "m12_q1",
                    "text": "Using the power rule, find the derivative of the function f(x) = 4x³ - 5x.",
                    "concept": "The Power Rule",
                    "expected_answer": "12x^2 - 5",
                    "hint": "Apply the power rule d/dx [x^n] = n * x^(n-1) to each term independently. Remember that the derivative of 4x³ involves 4 * 3, and the derivative of -5x is simply the coefficient -5.",
                    "solution": "1. Given Function: f(x) = 4x³ - 5x\n2. Step 1: Differentiate 4x³ using power rule: 4 * 3 * x^(3-1) = 12x²\n3. Step 2: Differentiate -5x: -5 * 1 = -5\n4. Step 3: Combine derivatives: f'(x) = 12x² - 5\n\nDirect Answer: 12x^2 - 5."
                }
            ],
            "finalExam": [
                { 
                  "qId": "m12_f1", 
                  "moduleOrigin": "Module 1: Power Rule Differentiation",
                  "text": "Find the derivative of the function f(x) = 2x³ + 4x with respect to x. (Provide the resulting algebraic expression without spaces, using ^ for powers, e.g. 6x^2+4)", 
                  "expected": "6x^2+4",
                  "formula": "d/dx [x^n] = n * x^(n-1)",
                  "misconception": "Student might forget to subtract 1 from the exponent or ignore the constant multiplier."
                }
            ]
        },
        "Undergraduate": {
            "cards": [
                {
                    "id": "mug_c1",
                    "topic": "Fundamental Theorem of Calculus",
                    "question": "How does the Fundamental Theorem of Calculus simplify bounded continuous integration?",
                    "answer": "• Fundamental Link: Formally connects differentiation and integration as inverse structural operations.\n• Resolution Rule: Proves that the definite integral of f(x) from a to b can be resolved by tracking the anti-derivative boundaries: F(b) - F(a)."
                },
                {
                    "id": "mug_c2",
                    "topic": "Eigenvalues & Eigenvectors",
                    "question": "What is the defining characteristic equation of an eigenvector v for a linear matrix transformation A?",
                    "answer": "• Matrix Transformation: An eigenvector v maintains its directional orientation when transformed by matrix A.\n• Characteristic Relation: Av = λv, where scalar λ represents the corresponding eigenvalue found via det(A - λI) = 0."
                },
                {
                    "id": "mug_c3",
                    "topic": "Multivariable Partial Derivatives",
                    "question": "What does the gradient vector ∇f represent for a scalar function of multiple variables f(x, y, z)?",
                    "answer": "• Partial Derivatives: Measures instantaneous rate of change along individual coordinate axes independently.\n• Gradient Direction: ∇f = (∂f/∂x, ∂f/∂y, ∂f/∂z) points in the direction of maximum rate of increase of the function."
                }
            ],
            "quizzes": [
                {
                    "id": "mug_q1",
                    "text": "Evaluate the definite integral of f(x) = 2x from x = 1 to x = 3 using the Fundamental Theorem of Calculus.",
                    "concept": "Fundamental Theorem of Calculus",
                    "expected_answer": "8",
                    "hint": "First determine the antiderivative F(x) of 2x (which is x²). Then evaluate F(3) - F(1) by substituting the upper and lower limits.",
                    "solution": "1. Given Integral: Integral from 1 to 3 of 2x dx\n2. Antiderivative: F(x) = x²\n3. Evaluate at Upper Limit: F(3) = 3² = 9\n4. Evaluate at Lower Limit: F(1) = 1² = 1\n5. Fundamental Theorem: F(3) - F(1) = 9 - 1 = 8\n\nDirect Answer: 8."
                }
            ],
            "finalExam": [
                { 
                  "qId": "mug_f1", 
                  "moduleOrigin": "Module 1: Bounded Integration Limits",
                  "text": "Evaluate the definite integral of the function f(x) = 3x² from x = 1 to x = 3. (Provide numerical integer only)", 
                  "expected": "26",
                  "formula": "Integral(a to b) f(x)dx = F(b) - F(a) where F'(x) = f(x)",
                  "misconception": "Student might evaluate the boundary as F(3) - F(0) or perform the integration power rule incorrectly."
                }
            ]
        }
    }
}
