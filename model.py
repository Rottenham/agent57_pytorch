import torch
import torch.nn as nn
import torch.nn.functional as F


# Convolutional Encording
class ConvEncoder(nn.Module):
    def __init__(self, units):
        super(ConvEncoder, self).__init__()
        
        self.conv1 = nn.Conv2d(4, 32, 8, stride=4)
        self.conv2 = nn.Conv2d(32, 64, 4, stride=2)
        self.conv3 = nn.Conv2d(64, 64, 3, stride=1)
        self.flatten = nn.Flatten()
        self.fc = nn.Linear(3136, units)

    def forward(self, x):
        
        x = F.relu(self.conv1(x))  # (b, 32, 20, 20)
        x = F.relu(self.conv2(x))  # (b, 64, 9, 9)
        x = F.relu(self.conv3(x))  # (b, 64, 7, 7)
        x = self.flatten(x)        # (b, 3136)
        x = self.fc(x)             # (b, units)
        return x

# intrinsic or extrinsic QNetwork
class QNetwork(nn.Module):
    def __init__(self, action_space, hidden=512, units=512, num_arms=32):
        super(QNetwork, self).__init__()
        
        self.action_space = action_space
        self.num_arms = num_arms

        self.conv_encoder = ConvEncoder(units)
        self.lstm = nn.LSTM(input_size=units+self.action_space+self.num_arms+2,
                            hidden_size=hidden,
                            batch_first=False)
        
        self.fc = nn.Linear(hidden, hidden)
        self.fc_adv = nn.Linear(hidden, action_space)
        self.fc_v = nn.Linear(hidden, 1)

    def forward(self, input, states, prev_action, prev_in_rewards, prev_ex_rewards, j):
        """
        Args:
          input (torch.tensor): state [b, n_frames, 84, 84]
          prev_action (torch.tensor): previous action [b]
          prev_in_rewards (torch.tensor): previous intrinsic reward [b]
          prev_ex_rewards (torch.tensor): previous extrinsic reward [b]
        """
        
        # (b, q_units)
        x = F.relu(self.conv_encoder(input))

        # (b, action_space)
        prev_action_onehot = F.one_hot(prev_action, num_classes=self.action_space)
        
        # (b, num_arms)
        j_onehot = F.one_hot(j, num_classes=self.num_arms)
        
        # (b, q_units+action_space+num_arms+2)
        x = torch.cat([x, prev_action_onehot, prev_in_rewards[:, None], prev_ex_rewards[:, None], j_onehot], dim=1)

        # (1, b, hidden)
        x, states = self.lstm(x.unsqueeze(0), states)

        # (b, action_space)
        A = self.fc_adv(x.squeeze(0))
        
        # (b, 1)
        V = self.fc_v(x.squeeze(0))
        
        # (b, action_space)
        Q = V.expand(-1, self.action_space) + A - A.mean(1, keepdim=True).expand(-1, self.action_space)

        return Q, states


class EmbeddingNet(nn.Module):
    def __init__(self, units=32):
        super(EmbeddingNet, self).__init__()
        
        self.conv_encoder = ConvEncoder(units)

    def forward(self, inputs):
        """
        Args:
          input (torch.tensor): state [b, n_frames, 84, 84]
        Returns:
          embeded state [b, emebed_units]
        """
        
        return F.relu(self.conv_encoder(inputs))


class EmbeddingClassifer(nn.Module):
    def __init__(self, action_space, hidden=128):
        super(EmbeddingClassifer, self).__init__()
        
        self.fc1 = nn.Linear(64, hidden)
        self.fc2 = nn.Linear(hidden, action_space)

    def forward(self, input1, input2):
        """
        Args:
          embeded state (torch.tensor): state [b, emebed_units]
        Returns:
          action probability [b, action_space]
        """
        
        x = torch.cat([input1, input2], dim=1)
        x = F.relu(self.fc1(x))
        x = F.softmax(self.fc2(x), dim=1)
        
        return x


class LifeLongNet(nn.Module):
    def __init__(self, units=128):
        super(LifeLongNet, self).__init__()
        
        self.conv_encoder = ConvEncoder(units)

    def forward(self, inputs):
        """
        Args:
          input (torch.tensor): state [b, n_frames, 84, 84]
        Returns:
          lifelong state [b, lifelong_units]
        """
        
        return self.conv_encoder(inputs)
