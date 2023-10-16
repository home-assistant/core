import random  # noqa: D100


class PerformanceTestResults:  # noqa: D101
    def randomize(self):  # noqa: D102
        num_iterations_1 = (random.randrange(350, 600) * 100) - 1
        self.mod_test_result = 16
        self.mod_test_iterations = int(num_iterations_1 / 100)

        num_iterations_2 = (random.randrange(563, 2000) * 100) - 1
        self.float_test_result = 59
        self.float_test_iterations = int(num_iterations_2 / 100)

        num_iterations_3 = (random.randrange(500, 2000) * 100) - 1
        self.sqrt_test_result = num_iterations_3 - 899
        self.sqrt_test_iterations = int(num_iterations_3 / 100)

        num_iterations_4 = (random.randrange(500, 1500) * 100) - 1
        self.trig_test_result = num_iterations_4
        self.trig_test_iterations = int(num_iterations_4 / 100)

        self.loop_test_result = random.randrange(8500, 16000)

    def to_string(self):  # noqa: D102
        values = [
            self.mod_test_result,
            self.mod_test_iterations,
            self.float_test_result,
            self.float_test_iterations,
            self.sqrt_test_result,
            self.sqrt_test_iterations,
            self.trig_test_result,
            self.trig_test_iterations,
            self.loop_test_result,
        ]

        return ",".join(map(str, values))
